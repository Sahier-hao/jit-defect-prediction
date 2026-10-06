"""Local API for imported commit features, fixed baseline, and risk review."""

import hashlib
import os
import uuid
from contextlib import asynccontextmanager
from datetime import timezone
from pathlib import Path
from typing import Annotated, Literal

import joblib
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from .data import MAX_BYTES, CommitRecord, parse_csv
from .demo import demo_csv
from .learning import explain, fit_baseline
from .store import Commit, Dataset, Model, Prediction, Store

ROOT = Path(__file__).resolve().parent.parent


def iso(timestamp):
    return (
        timestamp.replace(tzinfo=timezone.utc).isoformat()
        if timestamp.tzinfo is None
        else timestamp.astimezone(timezone.utc).isoformat()
    )


def dataset_json(dataset):
    return {
        key: getattr(dataset, key)
        for key in (
            "id",
            "name",
            "provenance",
            "label_policy",
            "source_sha256",
            "is_demo",
            "row_count",
            "labeled_count",
            "positive_count",
        )
    } | {"created_at": iso(dataset.created_at)}


class TrainRequest(BaseModel):
    dataset_id: str = Field(min_length=1, max_length=32)


def create_app(*, data_dir=None, database_url=None):
    store = Store(
        Path(data_dir or os.environ.get("JIT_DATA_DIR", ROOT / "runtime")),
        database_url or os.environ.get("JIT_DATABASE_URL"),
    )

    @asynccontextmanager
    async def lifespan(_):
        yield
        store.engine.dispose()

    app = FastAPI(title="JIT Review API", version="0.1.0", lifespan=lifespan)
    app.state.store = store

    @app.exception_handler(ValueError)
    async def invalid_input(_, error):
        return JSONResponse(status_code=422, content={"detail": str(error)})

    @app.exception_handler(SQLAlchemyError)
    async def storage_error(_, error):
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Local storage is unavailable; check the service log and storage configuration"
            },
        )

    def import_file(contents, name, provenance, label_policy, is_demo):
        if not all(value.strip() for value in (name, provenance, label_policy)):
            raise ValueError("name, provenance, and label_policy must be provided")
        records = parse_csv(contents)
        dataset = Dataset(
            id=uuid.uuid4().hex,
            name=name.strip(),
            provenance=provenance.strip(),
            label_policy=label_policy.strip(),
            source_sha256=hashlib.sha256(contents).hexdigest(),
            is_demo=is_demo,
            row_count=len(records),
            labeled_count=sum(row.label is not None for row in records),
            positive_count=sum(row.label == 1 for row in records),
        )
        with store.session.begin() as session:
            session.add(dataset)
            session.flush()
            session.add_all(
                [
                    Commit(
                        dataset_id=dataset.id,
                        commit_id=row.commit_id,
                        committed_at=row.committed_at,
                        label=row.label,
                        features=row.features,
                        message=row.message,
                    )
                    for row in records
                ]
            )
        return dataset_json(dataset)

    def load_artifact(model):
        try:
            artifact = store.artifact(model.id)
            if (
                hashlib.sha256(artifact.read_bytes()).hexdigest()
                != model.artifact_sha256
            ):
                raise ValueError("Artifact checksum mismatch")
            return joblib.load(artifact)
        except Exception as error:
            raise HTTPException(
                409, "Model artifact is missing or corrupt; train a new model version"
            ) from error

    def model_json(model, *, verify=True):
        status = "ready"
        if verify:
            try:
                load_artifact(model)
            except HTTPException:
                status = "artifact_unavailable"
        return {
            "id": model.id,
            "dataset_id": model.dataset_id,
            "created_at": iso(model.created_at),
            "metadata": model.model_metadata,
            "metrics": model.metrics,
            "status": status,
        }

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/api/datasets")
    def datasets():
        with store.session() as session:
            return [
                dataset_json(item)
                for item in session.scalars(
                    select(Dataset).order_by(Dataset.created_at.desc(), Dataset.id)
                )
            ]

    @app.post("/api/datasets/import", status_code=201)
    async def upload(
        file: Annotated[UploadFile, File()],
        name: Annotated[str, Form(min_length=1, max_length=100)],
        provenance: Annotated[str, Form(min_length=1, max_length=2000)],
        label_policy: Annotated[str, Form(min_length=1, max_length=2000)],
        is_demo: Annotated[bool, Form()] = False,
    ):
        contents = await file.read(MAX_BYTES + 1)
        return import_file(contents, name, provenance, label_policy, is_demo)

    @app.get("/api/demo.csv")
    def sample():
        return Response(
            content=demo_csv(),
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="synthetic_features.csv"'
            },
        )

    @app.post("/api/demo", status_code=201)
    def demo():
        contents = demo_csv()
        with store.session() as session:
            existing = session.scalar(
                select(Dataset).where(
                    Dataset.source_sha256 == hashlib.sha256(contents).hexdigest(),
                    Dataset.is_demo.is_(True),
                )
            )
            if existing:
                return dataset_json(existing)
        return import_file(
            contents,
            "Synthetic review example",
            "Deterministic synthetic features (seed 42); not ActiveMQ or SZZ data",
            "Synthetic labels for software smoke validation only",
            True,
        )

    @app.post("/api/models/train", status_code=201)
    def train(request: TrainRequest):
        with store.session() as session:
            dataset = session.get(Dataset, request.dataset_id)
            if dataset is None:
                raise HTTPException(404, "Dataset not found")
            commits = session.scalars(
                select(Commit).where(Commit.dataset_id == dataset.id)
            ).all()
            records = [
                CommitRecord(
                    item.commit_id,
                    item.committed_at.replace(tzinfo=timezone.utc)
                    if item.committed_at.tzinfo is None
                    else item.committed_at,
                    item.label,
                    item.features,
                    item.message,
                )
                for item in commits
            ]
            result = fit_baseline(records, is_demo=dataset.is_demo)
            model_id = uuid.uuid4().hex
            result.metadata.update(
                source_sha256=dataset.source_sha256,
                provenance=dataset.provenance,
                label_policy=dataset.label_policy,
                is_demo=dataset.is_demo,
            )
            artifact = store.artifact(model_id)
            temporary = artifact.with_suffix(".tmp")
            try:
                joblib.dump(result.pipeline, temporary)
                temporary.replace(artifact)
                model = Model(
                    id=model_id,
                    dataset_id=dataset.id,
                    model_metadata=result.metadata,
                    metrics=result.metrics,
                    test_predictions=result.test_predictions,
                    artifact_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
                )
                session.add(model)
                session.flush()
                session.add_all(
                    [
                        Prediction(
                            model_id=model_id,
                            commit_id=item["commit_id"],
                            probability=item["probability"],
                            scope=item["scope"],
                        )
                        for item in result.predictions
                    ]
                )
                session.commit()
            except Exception:
                session.rollback()
                temporary.unlink(missing_ok=True)
                artifact.unlink(missing_ok=True)
                raise
            return model_json(model, verify=False)

    @app.get("/api/models")
    def models(dataset_id: str | None = None):
        statement = select(Model).order_by(Model.created_at.desc(), Model.id)
        if dataset_id:
            statement = statement.where(Model.dataset_id == dataset_id)
        with store.session() as session:
            return [model_json(item) for item in session.scalars(statement)]

    @app.get("/api/models/{model_id}/evaluation")
    def evaluation(model_id: str):
        with store.session() as session:
            model = session.get(Model, model_id)
            if model is None:
                raise HTTPException(404, "Model not found")
            return {
                "model_id": model.id,
                "metrics": model.metrics,
                "metadata": model.model_metadata,
                "predictions": model.test_predictions,
            }

    @app.get("/api/risks")
    def risks(
        model_id: str,
        dataset_id: str | None = None,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        min_probability: float = Query(0, ge=0, le=1),
        search: str = Query("", max_length=128),
        scope: Literal["holdout", "all"] = "holdout",
    ):
        with store.session() as session:
            model = session.get(Model, model_id)
            if model is None:
                raise HTTPException(404, "Model not found; train the baseline first")
            if dataset_id and model.dataset_id != dataset_id:
                raise HTTPException(409, "Model belongs to a different dataset")
            load_artifact(model)
            conditions = [
                Prediction.model_id == model_id,
                Commit.dataset_id == model.dataset_id,
                Prediction.probability >= min_probability,
            ]
            if scope == "holdout":
                conditions.append(Prediction.scope == "holdout")
            if search:
                conditions.append(Commit.commit_id.contains(search, autoescape=True))
            statement = (
                select(Prediction, Commit)
                .join(Commit, Prediction.commit_id == Commit.commit_id)
                .where(*conditions)
            )
            total = session.scalar(
                select(func.count()).select_from(statement.subquery())
            )
            rows = session.execute(
                statement.order_by(Prediction.probability.desc(), Commit.commit_id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            items = [
                {
                    "commit_id": commit.commit_id,
                    "committed_at": iso(commit.committed_at),
                    "message": commit.message,
                    "probability": prediction.probability,
                    "risk_level": "high"
                    if prediction.probability >= 0.7
                    else "low"
                    if prediction.probability < 0.3
                    else "medium",
                    "scope": prediction.scope,
                    "effort": max(1, commit.features["la"] + commit.features["ld"]),
                    "label": commit.label,
                }
                for prediction, commit in rows
            ]
            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "model_id": model_id,
                "dataset_id": model.dataset_id,
            }

    @app.get("/api/models/{model_id}/commits/{commit_id}")
    def detail(model_id: str, commit_id: str):
        with store.session() as session:
            model = session.get(Model, model_id)
            if model is None:
                raise HTTPException(404, "Model not found")
            commit = session.get(Commit, (model.dataset_id, commit_id))
            prediction = session.get(Prediction, (model_id, commit_id))
            if commit is None or prediction is None:
                raise HTTPException(
                    404, "Commit has no available features or prediction"
                )
            explanation = explain(load_artifact(model), commit.features)
            return {
                "commit_id": commit.commit_id,
                "committed_at": iso(commit.committed_at),
                "message": commit.message,
                "label": commit.label,
                "scope": prediction.scope,
                "probability": prediction.probability,
                "model_id": model_id,
                "dataset_id": model.dataset_id,
                "features": commit.features,
                "explanation": explanation,
            }

    dist = ROOT / "frontend" / "dist"
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def index():
        if (dist / "index.html").is_file():
            return FileResponse(dist / "index.html")
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Build the frontend first: npm --prefix frontend install; npm --prefix frontend run build",
                "api_docs": "/docs",
            },
        )

    return app


app = create_app()
