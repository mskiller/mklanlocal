"use client";

import Link from "next/link";

import { useModuleRegistry } from "@/components/module-registry-provider";

const FIRST_WAVE_ADDON_IDS = [
  "metadata_privacy",
  "export_recipes",
  "background_removal",
  "upscale_restore",
  "object_erase",
] as const;

const COLLECTION_SCOPE_MODULES = new Set<string>(["export_recipes"]);

function scopeSupports(moduleId: string, scope: "asset" | "batch" | "collection") {
  if (scope === "collection") {
    return COLLECTION_SCOPE_MODULES.has(moduleId);
  }
  return FIRST_WAVE_ADDON_IDS.includes(moduleId as (typeof FIRST_WAVE_ADDON_IDS)[number]);
}

function buildHref(
  moduleId: string,
  payload: {
    assetId?: string;
    assetIds?: string[];
    collectionId?: string;
  }
) {
  const params = new URLSearchParams();
  if (payload.assetId) {
    params.set("assetId", payload.assetId);
  }
  if (payload.assetIds?.length) {
    params.set("assetIds", payload.assetIds.join(","));
  }
  if (payload.collectionId) {
    params.set("collectionId", payload.collectionId);
  }
  const query = params.toString();
  return `/modules/${moduleId}${query ? `?${query}` : ""}`;
}

export function AddonQuickActions({
  assetId,
  assetIds,
  collectionId,
  title = "Addon Tools",
}: {
  assetId?: string;
  assetIds?: string[];
  collectionId?: string;
  title?: string;
}) {
  const { modules } = useModuleRegistry();
  const scope: "asset" | "batch" | "collection" = collectionId ? "collection" : assetIds?.length ? "batch" : "asset";
  const enabledAddons = modules
    .filter((moduleItem) => moduleItem.kind === "addon" && moduleItem.enabled && moduleItem.status === "active")
    .filter((moduleItem) => scopeSupports(moduleItem.module_id, scope))
    .sort(
      (left, right) =>
        FIRST_WAVE_ADDON_IDS.indexOf(left.module_id as (typeof FIRST_WAVE_ADDON_IDS)[number]) -
          FIRST_WAVE_ADDON_IDS.indexOf(right.module_id as (typeof FIRST_WAVE_ADDON_IDS)[number]) ||
        left.name.localeCompare(right.name)
    );

  if (!enabledAddons.length) {
    return null;
  }

  return (
    <div className="stack">
      <p className="eyebrow">{title}</p>
      <div className="card-actions">
        {enabledAddons.map((moduleItem) => (
          <Link
            key={`${scope}-${moduleItem.module_id}`}
            href={buildHref(moduleItem.module_id, { assetId, assetIds, collectionId })}
            className="button ghost-button small-button"
          >
            {moduleItem.nav_label ?? moduleItem.name}
          </Link>
        ))}
      </div>
    </div>
  );
}
