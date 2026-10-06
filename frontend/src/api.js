export async function request(url, options = {}) {
  let response;
  try {
    response = await fetch(url, options);
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error(
      "Cannot reach the service. Check that the local API is running.",
    );
  }
  const text = await response.text();
  let result;
  try {
    result = text ? JSON.parse(text) : null;
  } catch {
    result = null;
  }
  if (!response.ok) {
    const detail = result?.detail;
    const message = Array.isArray(detail)
      ? detail
          .map(
            (item) => `${item.loc?.slice(1).join(".") || "Input"}: ${item.msg}`,
          )
          .join("; ")
      : typeof detail === "string"
        ? detail
        : `Service request failed (${response.status}). Please try again.`;
    throw new Error(message);
  }
  if (result === null && text)
    throw new Error("The service returned an unreadable response.");
  return result;
}
