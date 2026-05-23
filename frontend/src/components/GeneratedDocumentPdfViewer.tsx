import { FileText, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import {
  createGeneratedDocumentPdf,
  downloadGeneratedDocumentPdf
} from "../services/contractService";
import type { GeneratedDocument, GeneratedDocumentPdfArtifact } from "../types";
import { Button, Panel } from "./ui";

interface GeneratedDocumentPdfViewerProps {
  actions?: React.ReactNode;
  animated?: boolean;
  canCreatePdf?: boolean;
  clientScoped?: boolean;
  className?: string;
  displayFilename?: string;
  document?: GeneratedDocument;
  emptyDescription?: string;
  ensureLatestPdf?: boolean;
  onArtifactReady?: (artifact: GeneratedDocumentPdfArtifact) => void;
  revealDelay?: number;
  showEyebrow?: boolean;
  title?: string;
}

export function GeneratedDocumentPdfViewer({
  actions,
  animated = false,
  canCreatePdf = false,
  clientScoped = false,
  className = "",
  displayFilename,
  document,
  emptyDescription = "The generated PDF will appear here.",
  ensureLatestPdf = false,
  onArtifactReady,
  revealDelay = 0,
  showEyebrow = true,
  title = "Contract PDF"
}: GeneratedDocumentPdfViewerProps) {
  const [error, setError] = useState<string>();
  const [filename, setFilename] = useState<string>();
  const [isLoading, setIsLoading] = useState(false);
  const [pdfUrl, setPdfUrl] = useState<string>();
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | undefined;

    async function loadPdf() {
      setError(undefined);
      setPdfUrl(undefined);
      setFilename(undefined);

      if (!document) {
        setIsLoading(false);
        return;
      }

      if (!ensureLatestPdf && !hasPdfArtifact(document)) {
        setIsLoading(false);
        setError("PDF artifact is not available yet.");
        return;
      }

      setIsLoading(true);
      try {
        if (ensureLatestPdf || (canCreatePdf && !hasPdfArtifact(document))) {
          const artifact = await createGeneratedDocumentPdf(document.id, { clientScoped });
          if (!cancelled) onArtifactReady?.(artifact);
        }

        const result = await downloadGeneratedDocumentPdf(document.id, { clientScoped });
        objectUrl = URL.createObjectURL(result.blob);
        if (!cancelled) {
          setPdfUrl(objectUrl);
          setFilename(result.filename ?? document.pdf_filename ?? `contract-${document.contract_id}.pdf`);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(errorMessage(loadError, "Could not load generated PDF."));
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    void loadPdf();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [canCreatePdf, clientScoped, document?.id, ensureLatestPdf, reloadKey]);

  return (
    <Panel animated={animated} className={`flex h-full flex-col overflow-hidden lg:h-[740px] ${className}`} revealDelay={revealDelay}>
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-3">
        <div className="min-w-0">
          {showEyebrow ? (
            <p className="text-xs font-bold uppercase tracking-[0.12em] text-orange-600">
              UltraSafe Contract PDF
            </p>
          ) : null}
          <h2 className="mt-1 truncate text-sm font-bold text-slate-950">{title}</h2>
          {displayFilename || filename ? (
            <p className="mt-1 truncate text-xs font-semibold text-slate-500">{displayFilename ?? filename}</p>
          ) : null}
        </div>
        {document ? (
          <Button
            className="min-h-8 px-3 py-1 text-xs"
            disabled={isLoading}
            icon={RefreshCw}
            onClick={() => setReloadKey((current) => current + 1)}
          >
            Refresh
          </Button>
        ) : null}
      </div>
      <div className="min-h-0 flex-1 overflow-hidden rounded-lg border border-slate-200 bg-slate-100 p-2 shadow-inner">
        {pdfUrl ? (
          <iframe
            className="h-full w-full rounded-md bg-white"
            src={pdfUrl}
            title={title}
          />
        ) : (
          <div className="flex h-full min-h-[420px] items-center justify-center rounded-md bg-white text-center">
            <div className="max-w-sm px-6">
              <FileText className="mx-auto h-8 w-8 text-slate-300" />
              <p className="mt-3 text-sm font-bold text-slate-700">
                {isLoading ? "Preparing PDF preview..." : "No PDF preview available."}
              </p>
              <p className="mt-1 text-xs font-semibold text-slate-500">
                {error ?? emptyDescription}
              </p>
            </div>
          </div>
        )}
      </div>
      {actions ? <div className="mt-4 flex flex-wrap justify-end gap-2">{actions}</div> : null}
    </Panel>
  );
}

function hasPdfArtifact(document: GeneratedDocument) {
  return Boolean(
    document.pdf_storage_key ||
    document.pdf_filename ||
    document.pdf_content_hash ||
    document.pdf_generated_at
  );
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}


