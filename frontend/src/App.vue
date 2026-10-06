<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { request } from "./api.js";
import "./style.css";

const datasets = ref([]),
  datasetId = ref(""),
  models = ref([]),
  modelId = ref("");
const risks = ref(null),
  detail = ref(null),
  busy = ref(""),
  error = ref(""),
  loading = ref(false);
const search = ref(""),
  minProbability = ref("0"),
  scope = ref("holdout"),
  page = ref(1);
const importDialog = ref(null),
  fileInput = ref(null);
const importName = ref(""),
  provenance = ref(""),
  labelPolicy = ref(""),
  synthetic = ref(false);
const dataset = computed(() =>
  datasets.value.find((item) => item.id === datasetId.value),
);
const model = computed(() =>
  models.value.find((item) => item.id === modelId.value),
);
const pages = computed(() =>
  Math.max(1, Math.ceil((risks.value?.total || 0) / 15)),
);
const top = computed(
  () => detail.value?.explanation.contributions.slice(0, 5) || [],
);
const largest = computed(() =>
  Math.max(...top.value.map((item) => Math.abs(item.contribution)), 0.001),
);
let epoch = 0,
  riskSequence = 0,
  detailSequence = 0,
  timer;

const percent = (value) =>
  value == null ? "—" : `${(value * 100).toFixed(1)}%`;
const metric = (value) => (value == null ? "—" : value.toFixed(3));
const date = (value) =>
  new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value));
const shortId = (value) => value?.slice(0, 8) || "—";

async function loadRisks() {
  const current = epoch,
    sequence = ++riskSequence,
    selected = modelId.value;
  if (!selected) {
    risks.value = null;
    loading.value = false;
    return;
  }
  loading.value = true;
  try {
    const query = new URLSearchParams({
      model_id: selected,
      dataset_id: datasetId.value,
      page: page.value,
      page_size: 15,
      min_probability: minProbability.value,
      search: search.value,
      scope: scope.value,
    });
    const result = await request(`/api/risks?${query}`);
    if (current === epoch && sequence === riskSequence) risks.value = result;
  } catch (failure) {
    if (current === epoch && sequence === riskSequence) {
      error.value = failure.message;
      risks.value = null;
    }
  } finally {
    if (current === epoch && sequence === riskSequence) loading.value = false;
  }
}

async function chooseDataset(id) {
  const current = ++epoch;
  ++detailSequence;
  datasetId.value = id;
  modelId.value = "";
  models.value = [];
  risks.value = null;
  detail.value = null;
  page.value = 1;
  if (!id) return;
  try {
    const result = await request(
      `/api/models?dataset_id=${encodeURIComponent(id)}`,
    );
    if (current !== epoch) return;
    models.value = result;
    modelId.value = result.find((item) => item.status === "ready")?.id || "";
    await loadRisks();
  } catch (failure) {
    if (current === epoch) error.value = failure.message;
  }
}

async function chooseModel(id) {
  ++epoch;
  ++detailSequence;
  modelId.value = id;
  detail.value = null;
  risks.value = null;
  page.value = 1;
  error.value = "";
  await loadRisks();
}

async function refresh(selected) {
  datasets.value = await request("/api/datasets");
  await chooseDataset(selected || datasets.value[0]?.id || "");
}

async function action(label, work) {
  if (busy.value) return;
  busy.value = label;
  error.value = "";
  try {
    await work();
  } catch (failure) {
    error.value = failure.message;
  } finally {
    busy.value = "";
  }
}

async function loadDemo() {
  await action("Loading demo", async () => {
    const imported = await request("/api/demo", { method: "POST" });
    await refresh(imported.id);
  });
}

async function train() {
  await action("Training baseline", async () => {
    await request("/api/models/train", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dataset_id: datasetId.value }),
    });
    await chooseDataset(datasetId.value);
  });
}

async function inspect(commitId) {
  const current = epoch,
    sequence = ++detailSequence;
  detail.value = null;
  try {
    const result = await request(
      `/api/models/${modelId.value}/commits/${encodeURIComponent(commitId)}`,
    );
    if (current === epoch && sequence === detailSequence) detail.value = result;
  } catch (failure) {
    if (current === epoch && sequence === detailSequence)
      error.value = failure.message;
  }
}

function openImport() {
  error.value = "";
  importDialog.value.showModal();
}
async function importCsv() {
  await action("Importing dataset", async () => {
    const file = fileInput.value.files[0];
    if (!file) throw new Error("Choose a UTF-8 feature CSV first.");
    const form = new FormData();
    form.set("file", file);
    form.set("name", importName.value);
    form.set("provenance", provenance.value);
    form.set("label_policy", labelPolicy.value);
    form.set("is_demo", String(synthetic.value));
    const imported = await request("/api/datasets/import", {
      method: "POST",
      body: form,
    });
    importDialog.value.close();
    await refresh(imported.id);
    importName.value = "";
    provenance.value = "";
    labelPolicy.value = "";
    synthetic.value = false;
    fileInput.value.value = "";
  });
}

function nextPage(value) {
  page.value = value;
  loadRisks();
}
watch([search, minProbability, scope], () => {
  clearTimeout(timer);
  timer = setTimeout(() => {
    page.value = 1;
    loadRisks();
  }, 200);
});
onMounted(() => action("Opening workspace", () => refresh()));
onUnmounted(() => {
  clearTimeout(timer);
  ++epoch;
  ++riskSequence;
  ++detailSequence;
});
</script>

<template>
  <div class="workspace">
    <aside class="sidebar">
      <a class="brand" href="/" aria-label="JIT Review home"
        ><span class="brand-mark">J</span><span>JIT <b>Review</b></span></a
      >
      <div class="sidebar-caption">COMMIT INTELLIGENCE</div>
      <div class="nav-active">
        <span class="nav-icon">▦</span> Risk workspace
        <span class="nav-dot"></span>
      </div>
      <div class="sidebar-section">
        <label for="dataset-select">DATASET</label>
        <select
          id="dataset-select"
          aria-label="Select dataset"
          :value="datasetId"
          :disabled="!!busy"
          @change="chooseDataset($event.target.value)"
        >
          <option v-if="!datasets.length" value="">No datasets yet</option>
          <option v-for="item in datasets" :key="item.id" :value="item.id">
            {{ item.name }}
          </option>
        </select>
        <template v-if="dataset">
          <span class="source-tag" :class="{ synthetic: dataset.is_demo }">{{
            dataset.is_demo ? "SYNTHETIC DATA" : "IMPORTED DATA"
          }}</span>
          <p class="sidebar-description">
            {{ dataset.row_count.toLocaleString() }} commits ·
            {{ dataset.labeled_count.toLocaleString() }} labeled
          </p>
          <p class="sidebar-description muted">{{ dataset.provenance }}</p>
        </template>
        <button class="sidebar-button" :disabled="!!busy" @click="openImport">
          + Import CSV
        </button>
        <button class="sidebar-link" :disabled="!!busy" @click="loadDemo">
          Load synthetic demo
        </button>
      </div>
      <div class="sidebar-bottom">
        <span class="status-light"></span> Local research workspace
        <p>Baseline v0.1 · All dates in UTC</p>
        <a href="/docs" target="_blank" rel="noopener">API reference ↗</a>
      </div>
    </aside>

    <main class="main-content">
      <header class="topbar">
        <span>WORKSPACE <span class="breadcrumb">/</span> RISK REVIEW</span
        ><span class="local-badge">LOCAL BASELINE</span>
      </header>
      <div class="page-content">
        <div class="page-heading">
          <div>
            <p class="eyebrow">REVIEW WITH INTENT</p>
            <h1>Put attention where it matters.</h1>
            <p class="subtitle">
              A clear view of commit risk, with the evidence behind every score.
            </p>
          </div>
          <button
            class="button secondary"
            :disabled="!!busy"
            @click="openImport"
          >
            Import CSV
          </button>
        </div>
        <div
          v-if="error && !importDialog?.open"
          class="error-banner"
          role="alert"
        >
          <span>{{ error }}</span
          ><button aria-label="Dismiss error" @click="error = ''">×</button>
        </div>
        <div v-if="busy" class="progress-note" role="status">
          <span class="spinner"></span>{{ busy }}…
        </div>

        <section v-if="!dataset && !busy" class="welcome">
          <div class="welcome-symbol">01 / START</div>
          <h2>Start with your commit history</h2>
          <p>
            Import a CSV of commit features and labels, or explore the workflow
            with a clearly marked synthetic example.
          </p>
          <div class="welcome-actions">
            <button class="button primary" @click="loadDemo">
              Load synthetic demo</button
            ><button class="button secondary" @click="openImport">
              Choose a feature CSV
            </button>
          </div>
          <div class="welcome-path">
            <span>01 · Import features</span><span>02 · Train a baseline</span
            ><span>03 · Review risk</span>
          </div>
        </section>

        <template v-if="dataset">
          <div v-if="dataset.is_demo" class="demo-notice">
            <span class="notice-dot"></span
            ><strong>Synthetic example.</strong> Scores come from a trained
            model; these data demonstrate the workflow and do not measure real
            project performance.
          </div>
          <section class="model-bar">
            <div>
              <p class="eyebrow">ACTIVE BASELINE</p>
              <div class="model-name">
                Logistic regression
                <span class="model-type">14 change features</span>
              </div>
            </div>
            <div class="model-actions">
              <select
                v-if="models.length"
                aria-label="Select model"
                :value="modelId"
                :disabled="!!busy"
                @change="chooseModel($event.target.value)"
              >
                <option v-if="!modelId" value="">Choose a ready model</option>
                <option
                  v-for="item in models"
                  :key="item.id"
                  :value="item.id"
                  :disabled="item.status !== 'ready'"
                >
                  {{ shortId(item.id) }} ·
                  {{
                    item.status === "ready"
                      ? date(item.created_at)
                      : "Artifact unavailable"
                  }}
                </option></select
              ><button class="button primary" :disabled="!!busy" @click="train">
                Train baseline
              </button>
            </div>
          </section>

          <section v-if="!model" class="empty-state">
            <h2>Train the first model for this dataset.</h2>
            <p>
              The baseline uses earlier commits for training and later commits
              for evaluation. Unknown labels are excluded.
            </p>
            <p v-if="!dataset.is_demo" class="small-note">
              Real-data gate: at least 1,000 labeled commits and 50 positive
              labels.
            </p>
          </section>

          <template v-if="model">
            <section class="metrics" aria-label="Model evaluation">
              <div class="metric-card">
                <span>ROC-AUC</span
                ><strong>{{ metric(model.metrics.roc_auc) }}</strong>
                <p>
                  {{ model.metrics.notes.roc_auc || "Held-out discrimination" }}
                </p>
              </div>
              <div class="metric-card">
                <span>F1 score</span
                ><strong>{{ metric(model.metrics.f1) }}</strong>
                <p>
                  Precision {{ metric(model.metrics.precision) }} · Recall
                  {{ metric(model.metrics.recall) }}
                </p>
              </div>
              <div class="metric-card emphasis">
                <span>Recall @ 20% effort</span
                ><strong>{{
                  percent(model.metrics.recall_at_20_effort)
                }}</strong>
                <p>
                  {{
                    model.metrics.notes.recall_at_20_effort ||
                    "Whole commits within review budget"
                  }}
                </p>
              </div>
              <div class="metric-card">
                <span>Popt</span
                ><strong>{{ metric(model.metrics.popt) }}</strong>
                <p>
                  {{
                    model.metrics.notes.popt ||
                    "Normalized full-curve review value"
                  }}
                </p>
              </div>
            </section>
            <div class="split-note">
              <span class="status-light"></span
              >{{ model.metadata.train_count }} training /
              {{ model.metadata.test_count }} test ·
              {{ model.metadata.excluded_unknown }} unknown excluded<span
                >Split {{ date(model.metadata.split_at) }} · Seed
                {{ model.metadata.seed }}</span
              >
            </div>
            <div class="review-layout" :class="{ 'with-detail': detail }">
              <section class="risk-section">
                <div class="section-heading">
                  <div>
                    <p class="eyebrow">REVIEW QUEUE</p>
                    <h2>
                      Commits to inspect
                      <span class="count-badge">{{ risks?.total || 0 }}</span>
                    </h2>
                  </div>
                  <span class="sorted-note">Highest probability first ↓</span>
                </div>
                <div class="filters">
                  <label class="search-field"
                    ><span class="sr-only">Search commit ID</span
                    ><input
                      v-model="search"
                      placeholder="Search commit ID…"
                      aria-label="Search commit ID" /></label
                  ><select
                    v-model="minProbability"
                    aria-label="Minimum risk probability"
                  >
                    <option value="0">All risk levels</option>
                    <option value="0.3">Medium + high</option>
                    <option value="0.7">High risk only</option></select
                  ><select v-model="scope" aria-label="Evaluation scope">
                    <option value="holdout">Holdout period</option>
                    <option value="all">All periods</option>
                  </select>
                </div>
                <p v-if="scope === 'all'" class="scope-warning">
                  Training-period scores are fit checks. They are not held-out
                  evaluation.
                </p>
                <div v-if="loading" class="table-loading" role="status">
                  Loading ranked commits…
                </div>
                <div v-else-if="risks?.items.length" class="table-scroll">
                  <table aria-label="Commit risk list">
                    <thead>
                      <tr>
                        <th>COMMIT / CHANGE</th>
                        <th>PROBABILITY</th>
                        <th>RISK</th>
                        <th>EFFORT</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="item in risks.items"
                        :key="item.commit_id"
                        :class="{
                          selected: detail?.commit_id === item.commit_id,
                        }"
                      >
                        <td>
                          <span class="commit-id">{{ item.commit_id }}</span>
                          <p class="commit-message">
                            {{ item.message || "No message supplied" }}
                          </p>
                          <span class="commit-date"
                            >{{ date(item.committed_at) }}
                            <span
                              v-if="item.scope === 'training'"
                              class="training-tag"
                              >TRAINING</span
                            ></span
                          >
                        </td>
                        <td>
                          <div class="score-value">
                            {{ percent(item.probability) }}
                          </div>
                          <div class="score-track">
                            <i
                              :class="item.risk_level"
                              :style="{ width: percent(item.probability) }"
                            ></i>
                          </div>
                        </td>
                        <td>
                          <span class="risk-tag" :class="item.risk_level">{{
                            item.risk_level
                          }}</span>
                        </td>
                        <td class="effort-value">
                          {{ item.effort.toLocaleString() }}<span>lines</span>
                        </td>
                        <td>
                          <button
                            class="inspect-button"
                            :aria-label="`Inspect ${item.commit_id}`"
                            @click="inspect(item.commit_id)"
                          >
                            ↗
                          </button>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div v-else-if="risks" class="empty-results">
                  No commits match these filters.
                </div>
                <div v-else-if="!error" class="empty-results">
                  Choose a model to load its review queue.
                </div>
                <div v-if="risks" class="pagination">
                  <span
                    >Page {{ page }} of {{ pages }} ·
                    {{ risks.total }} commits</span
                  >
                  <div>
                    <button
                      :disabled="page <= 1 || loading"
                      aria-label="Previous page"
                      @click="nextPage(page - 1)"
                    >
                      ←</button
                    ><button
                      :disabled="page >= pages || loading"
                      aria-label="Next page"
                      @click="nextPage(page + 1)"
                    >
                      →
                    </button>
                  </div>
                </div>
              </section>

              <aside
                v-if="detail"
                class="detail-panel"
                aria-label="Commit detail"
              >
                <div class="detail-header">
                  <p class="eyebrow">COMMIT DETAIL</p>
                  <button
                    aria-label="Close commit detail"
                    @click="detail = null"
                  >
                    ×
                  </button>
                </div>
                <div class="detail-id">{{ detail.commit_id }}</div>
                <p class="detail-message">{{ detail.message }}</p>
                <div class="detail-score">
                  <strong>{{ percent(detail.probability) }}</strong
                  ><span>predicted defect risk</span>
                </div>
                <div class="detail-divider"></div>
                <h2>Why this score?</h2>
                <p class="explanation-subtitle">Exact linear contributions</p>
                <p class="small-note">
                  Contribution direction is relative to the model baseline, in
                  log-odds. It describes the model, not a cause of a defect.
                </p>
                <div class="contribution-list">
                  <div
                    v-for="item in top"
                    :key="item.feature"
                    class="contribution"
                  >
                    <div>
                      <strong>{{ item.feature.toUpperCase() }}</strong
                      ><span>{{ item.value.toLocaleString() }}</span
                      ><b :class="item.direction"
                        >{{ item.contribution >= 0 ? "+" : ""
                        }}{{ item.contribution.toFixed(3) }}</b
                      >
                    </div>
                    <div class="contribution-track">
                      <i
                        :class="item.direction"
                        :style="{
                          width: `${(Math.abs(item.contribution) / largest) * 100}%`,
                        }"
                      ></i>
                    </div>
                  </div>
                </div>
                <div class="detail-legend">
                  <span><i class="legend-raises"></i> Raises risk</span
                  ><span><i class="legend-lowers"></i> Lowers risk</span>
                </div>
                <dl class="detail-meta">
                  <dt>Model version</dt>
                  <dd>{{ shortId(detail.model_id) }}</dd>
                  <dt>Data period</dt>
                  <dd>{{ detail.scope }}</dd>
                  <dt>Historical label</dt>
                  <dd>
                    {{
                      detail.label == null
                        ? "unknown"
                        : detail.label === 1
                          ? "defect-labeled"
                          : "non-defect-labeled"
                    }}
                  </dd>
                  <dt>Baseline log-odds</dt>
                  <dd>{{ detail.explanation.baseline.toFixed(3) }}</dd>
                </dl>
                <details class="all-features">
                  <summary>All 14 features</summary>
                  <dl>
                    <template v-for="(value, key) in detail.features" :key="key"
                      ><dt>{{ key.toUpperCase() }}</dt>
                      <dd>{{ value }}</dd></template
                    >
                  </dl>
                </details>
              </aside>
            </div>
            <p class="footnote">
              Effort = max(1, added + deleted lines). Evaluation ranks by
              probability / effort; the review queue ranks by probability.
              <a
                :href="`/api/models/${model.id}/evaluation`"
                target="_blank"
                rel="noopener"
                >View evaluation evidence ↗</a
              >
            </p>
          </template>
        </template>
      </div>
    </main>

    <dialog
      ref="importDialog"
      class="import-dialog"
      aria-labelledby="import-title"
      @cancel="!busy && importDialog.close()"
    >
      <form @submit.prevent="importCsv">
        <p class="eyebrow">BRING YOUR OWN DATA</p>
        <h2 id="import-title">Import feature CSV</h2>
        <p class="small-note">
          UTF-8 · 14 Kamei features · timezone-aware dates · labels 0 / 1 /
          unknown. Maximum 5 MiB and 20,000 rows.
        </p>
        <label
          >Dataset name<input
            v-model="importName"
            required
            maxlength="100"
            :disabled="!!busy" /></label
        ><label
          >Data source / provenance<textarea
            v-model="provenance"
            required
            maxlength="2000"
            rows="2"
            :disabled="!!busy"
          ></textarea></label
        ><label
          >Label policy<textarea
            v-model="labelPolicy"
            required
            maxlength="2000"
            rows="2"
            placeholder="Describe how labels were created and their observation window"
            :disabled="!!busy"
          ></textarea></label
        ><label
          >Feature CSV<input
            ref="fileInput"
            type="file"
            accept=".csv,text/csv"
            required
            :disabled="!!busy" /></label
        ><label class="checkbox-label"
          ><input v-model="synthetic" type="checkbox" :disabled="!!busy" />This
          is synthetic / demo data</label
        >
        <p class="small-note">
          <a href="/api/demo.csv" download>Download a synthetic sample CSV ↗</a>
        </p>
        <div v-if="error" class="error-banner" role="alert">{{ error }}</div>
        <div class="dialog-actions">
          <button
            type="button"
            class="button secondary"
            :disabled="!!busy"
            @click="importDialog.close()"
          >
            Cancel</button
          ><button class="button primary" :disabled="!!busy">
            {{ busy === "Importing dataset" ? "Importing…" : "Import dataset" }}
          </button>
        </div>
      </form>
    </dialog>
  </div>
</template>
