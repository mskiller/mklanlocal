"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth-provider";
import { ImageCropperModal } from "@/components/image-cropper-modal";
import { useToast } from "@/components/use-toast";
import { fetchSources, uploadEditedToSource, uploadToSource } from "@/lib/api";
import { CropSpec, Source, SourceUploadResponse } from "@/lib/types";

type OriginalUploadQueueItem = {
  id: string;
  kind: "original";
  file: File;
  previewUrl: string;
};

type CropUploadQueueItem = {
  id: string;
  kind: "crop";
  sourceItemId: string;
  file: File;
  previewUrl: string;
  crop: CropSpec;
  derivedName: string;
};

type UploadQueueItem = OriginalUploadQueueItem | CropUploadQueueItem;

function createQueueId(prefix: string) {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function buildCropFilename(filename: string) {
  const dotIndex = filename.lastIndexOf(".");
  if (dotIndex <= 0) {
    return `${filename}-crop`;
  }
  return `${filename.slice(0, dotIndex)}-crop${filename.slice(dotIndex)}`;
}

function revokeQueuePreviews(items: UploadQueueItem[]) {
  items.forEach((item) => URL.revokeObjectURL(item.previewUrl));
}

export default function UploadPage() {
  const { user } = useAuth();
  const { push } = useToast();
  const [sources, setSources] = useState<Source[]>([]);
  const [folder, setFolder] = useState("");
  const [queueItems, setQueueItems] = useState<UploadQueueItem[]>([]);
  const [result, setResult] = useState<SourceUploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [editingItemId, setEditingItemId] = useState<string | null>(null);
  const queueItemsRef = useRef<UploadQueueItem[]>([]);

  useEffect(() => {
    const load = async () => {
      try {
        setSources(await fetchSources());
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : "Unable to load sources.");
      }
    };
    void load();
  }, []);

  useEffect(() => {
    queueItemsRef.current = queueItems;
  }, [queueItems]);

  useEffect(() => {
    return () => {
      revokeQueuePreviews(queueItemsRef.current);
    };
  }, []);

  const uploadSource = useMemo(
    () => sources.find((source) => source.name.toLowerCase() === "upload"),
    [sources]
  );
  const originalItems = queueItems.filter((item): item is OriginalUploadQueueItem => item.kind === "original");
  const cropItems = queueItems.filter((item): item is CropUploadQueueItem => item.kind === "crop");
  const editingItem = queueItems.find((item) => item.id === editingItemId) ?? null;
  const editingImageSrc =
    editingItem?.kind === "crop"
      ? queueItems.find((item): item is OriginalUploadQueueItem => item.kind === "original" && item.id === editingItem.sourceItemId)?.previewUrl ?? null
      : editingItem?.previewUrl ?? null;

  if (user && !user.capabilities.can_upload_assets) {
    return (
      <AppShell title="Upload" description="Send new images into the managed upload source.">
        <section className="panel empty-state">
          <h2>Upload access required</h2>
          <p className="subdued">This page is available to admin and curator accounts.</p>
        </section>
      </AppShell>
    );
  }

  return (
    <AppShell
      title="Upload"
      description="Upload new media into the inbox-backed upload source. Files land in review first, then can be approved into a target library source."
      actions={
        uploadSource ? (
          <div className="page-actions">
            <Link href={`/sources/${uploadSource.id}`} className="button subtle-button small-button">
              Open Upload Source
            </Link>
            <Link href="/inbox" className="button ghost-button small-button">
              Open Inbox
            </Link>
          </div>
        ) : undefined
      }
    >
      <ImageCropperModal
        open={editingItem !== null}
        title={editingItem?.kind === "crop" ? editingItem.derivedName : editingItem?.file.name ?? "Crop upload"}
        imageSrc={editingImageSrc}
        initialCrop={editingItem?.kind === "crop" ? editingItem.crop : null}
        confirmLabel={editingItem?.kind === "crop" ? "Save Crop Draft" : "Add Cropped Draft"}
        busyLabel="Saving..."
        onClose={() => setEditingItemId(null)}
        onConfirm={async ({ crop, previewBlob }) => {
          if (!editingItem) {
            return;
          }
          if (editingItem.kind === "original" && !previewBlob) {
            return;
          }
          const nextPreviewUrl = previewBlob ? URL.createObjectURL(previewBlob) : editingItem.previewUrl;
          if (editingItem.kind === "crop") {
            const previousPreviewUrl = editingItem.previewUrl;
            setQueueItems((current) =>
              current.map((item) =>
                item.id === editingItem.id
                  ? {
                      ...item,
                      crop,
                      previewUrl: nextPreviewUrl,
                    }
                  : item
              )
            );
            if (nextPreviewUrl !== previousPreviewUrl) {
              URL.revokeObjectURL(previousPreviewUrl);
            }
          } else {
            setQueueItems((current) => [
              ...current,
              {
                id: createQueueId("crop"),
                kind: "crop",
                sourceItemId: editingItem.id,
                file: editingItem.file,
                previewUrl: nextPreviewUrl,
                crop,
                derivedName: buildCropFilename(editingItem.file.name),
              },
            ]);
          }
          setEditingItemId(null);
        }}
      />
      <section className="two-column">
        <form
          className="panel form-grid"
          onSubmit={async (event: FormEvent) => {
            event.preventDefault();
            if (!uploadSource || !queueItems.length) {
              return;
            }
            setSubmitting(true);
            setError(null);
            setResult(null);
            try {
              const responses: SourceUploadResponse[] = [];
              if (originalItems.length) {
                responses.push(await uploadToSource(uploadSource.id, originalItems.map((item) => item.file), folder));
              }
              if (cropItems.length) {
                const cropResponses = await Promise.all(
                  cropItems.map((item) => uploadEditedToSource(uploadSource.id, item.file, item.crop, folder))
                );
                responses.push(...cropResponses);
              }
              const combined: SourceUploadResponse = {
                source_id: uploadSource.id,
                folder: responses.find((entry) => entry.folder)?.folder ?? folder.trim(),
                uploaded_files: responses.flatMap((entry) => entry.uploaded_files),
                scan_job_id: responses.find((entry) => entry.scan_job_id)?.scan_job_id ?? null,
              };
              setResult(combined);
              revokeQueuePreviews(queueItemsRef.current);
              setQueueItems([]);
              setFolder("");
              push(`Uploaded ${combined.uploaded_files.length} file${combined.uploaded_files.length === 1 ? "" : "s"} to Inbox.`);
            } catch (nextError) {
              setError(nextError instanceof Error ? nextError.message : "Unable to upload files.");
            } finally {
              setSubmitting(false);
            }
          }}
        >
          <div>
            <p className="eyebrow">Upload Source</p>
            <h2>{uploadSource?.name ?? "Preparing upload source"}</h2>
            <p className="subdued">{uploadSource?.display_root_path ?? "Waiting for the system upload source to appear."}</p>
          </div>
          <label className="field">
            <span>Subfolder inside upload source</span>
            <input
              value={folder}
              onChange={(event) => setFolder(event.target.value)}
              placeholder="optional/subfolder"
            />
          </label>
          <label className="field">
            <span>Images</span>
            <input
              type="file"
              accept="image/*"
              multiple
              onChange={(event) => {
                const files = Array.from(event.target.files ?? []);
                if (!files.length) {
                  return;
                }
                revokeQueuePreviews(queueItemsRef.current);
                setQueueItems(
                  files.map((file) => ({
                    id: createQueueId("original"),
                    kind: "original",
                    file,
                    previewUrl: URL.createObjectURL(file),
                  }))
                );
                setResult(null);
                setError(null);
                event.currentTarget.value = "";
              }}
            />
          </label>
          <div className="chip-row">
            <span className="chip">{originalItems.length} original{originalItems.length === 1 ? "" : "s"}</span>
            <span className="chip">{cropItems.length} crop draft{cropItems.length === 1 ? "" : "s"}</span>
            {folder ? <span className="chip">Folder: {folder}</span> : <span className="chip">Root folder</span>}
          </div>
          <div className="list-stack compact-list-stack upload-queue-list">
            {queueItems.length ? (
              queueItems.map((item) => {
                const linkedCropCount =
                  item.kind === "original"
                    ? cropItems.filter((crop) => crop.sourceItemId === item.id).length
                    : 0;
                return (
                  <div key={item.id} className="upload-queue-row">
                    <img src={item.previewUrl} alt={item.kind === "crop" ? item.derivedName : item.file.name} className="upload-queue-preview" />
                    <div className="stack" style={{ minWidth: 0 }}>
                      <div className="row-between">
                        <strong>{item.kind === "crop" ? item.derivedName : item.file.name}</strong>
                        <span className="chip">{item.kind === "crop" ? "Crop Draft" : "Original"}</span>
                      </div>
                      <p className="subdued">
                        {item.kind === "crop"
                          ? `Derived from ${item.file.name}`
                          : linkedCropCount
                            ? `${linkedCropCount} crop draft${linkedCropCount === 1 ? "" : "s"} attached`
                            : "Ready to upload as-is"}
                      </p>
                      <div className="card-actions">
                        <button
                          type="button"
                          className="button subtle-button small-button"
                          onClick={() => setEditingItemId(item.id)}
                        >
                          {item.kind === "crop" ? "Re-edit Crop" : "Create Crop"}
                        </button>
                        <button
                          type="button"
                          className="button ghost-button small-button"
                          onClick={() => {
                            setQueueItems((current) => {
                              const removeIds = new Set<string>([item.id]);
                              if (item.kind === "original") {
                                current
                                  .filter((entry): entry is CropUploadQueueItem => entry.kind === "crop" && entry.sourceItemId === item.id)
                                  .forEach((entry) => removeIds.add(entry.id));
                              }
                              const removed = current.filter((entry) => removeIds.has(entry.id));
                              revokeQueuePreviews(removed);
                              return current.filter((entry) => !removeIds.has(entry.id));
                            });
                            if (editingItemId === item.id || (item.kind === "original" && cropItems.some((crop) => crop.sourceItemId === item.id && crop.id === editingItemId))) {
                              setEditingItemId(null);
                            }
                          }}
                        >
                          {item.kind === "crop" ? "Remove Crop" : "Remove Original"}
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })
            ) : (
              <p className="subdued">Choose one or more images, then add optional cropped drafts before uploading.</p>
            )}
          </div>
          <button className="button" type="submit" disabled={!uploadSource || !queueItems.length || submitting}>
            {submitting ? "Uploading..." : "Upload Queue"}
          </button>
          {error ? <p className="subdued">{error}</p> : null}
        </form>

        <section className="panel stack">
          <div>
            <p className="eyebrow">What Happens Next</p>
            <h2>Server-side intake</h2>
          </div>
          <div className="metadata-grid">
            <div className="metadata-row">
              <strong>Storage</strong>
              <div className="subdued">Files go only into the dedicated `upload` source on the server.</div>
            </div>
            <div className="metadata-row">
              <strong>Crops</strong>
              <div className="subdued">Crop drafts keep the original file in the queue and create separate inbox entries with a `-crop` filename.</div>
            </div>
            <div className="metadata-row">
              <strong>Indexing</strong>
              <div className="subdued">Uploads enter the inbox review flow. Approving an item moves it into a target source and queues the scan.</div>
            </div>
            <div className="metadata-row">
              <strong>Permissions</strong>
              <div className="subdued">Curators can upload and prepare crop drafts without getting source or database admin rights.</div>
            </div>
          </div>
          {result ? (
            <section className="panel stack">
              <div>
                <p className="eyebrow">Upload Complete</p>
                <h2>{result.uploaded_files.length} file{result.uploaded_files.length === 1 ? "" : "s"} added</h2>
              </div>
              <div className="chip-row">
                {result.scan_job_id ? <span className="chip">Scan queued</span> : <span className="chip">Inbox review required</span>}
                <span className="chip">{result.folder || "root folder"}</span>
              </div>
              <div className="list-stack compact-list-stack">
                {result.uploaded_files.map((file) => (
                  <div key={file} className="metadata-row">
                    <strong>{file}</strong>
                  </div>
                ))}
              </div>
              <div className="card-actions">
                {uploadSource ? (
                  <Link href={`/sources/${uploadSource.id}${result.folder ? `?path=${encodeURIComponent(result.folder)}` : ""}`} className="button subtle-button small-button">
                    Open Uploaded Folder
                  </Link>
                ) : null}
                <Link href="/inbox" className="button ghost-button small-button">
                  Review Inbox
                </Link>
              </div>
            </section>
          ) : null}
        </section>
      </section>
    </AppShell>
  );
}
