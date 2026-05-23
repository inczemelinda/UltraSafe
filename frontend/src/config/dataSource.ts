const envMockFlag = import.meta.env.VITE_USE_MOCK_API;
const envLegalReviewMockFlag = import.meta.env.VITE_USE_MOCK_LEGAL_REVIEW_API;
const envBackendPricingFlag = import.meta.env.VITE_BACKEND_PRICING;

export const USE_MOCK_DATA = envMockFlag === "true";
export const USE_MOCK_LEGAL_REVIEW_DATA =
  envLegalReviewMockFlag == null ? false : envLegalReviewMockFlag !== "false";
export const USE_BACKEND_PRICING =
  envBackendPricingFlag == null ? true : envBackendPricingFlag !== "false";

export type DataSourceMode = "mock" | "backend";

export const DATA_SOURCE_MODE: DataSourceMode = USE_MOCK_DATA ? "mock" : "backend";
export const SHOW_MOCK_DATA_INDICATOR = USE_MOCK_DATA && import.meta.env.DEV;

if (USE_MOCK_DATA && typeof console !== "undefined") {
  console.warn(
    "[UltraSafe] Mock data mode is enabled. Frontend services will use local mock/localStorage data instead of the backend API. Set VITE_USE_MOCK_API=false or unset it to use backend mode."
  );
}

