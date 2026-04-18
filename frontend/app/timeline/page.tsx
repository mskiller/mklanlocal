"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { useModuleRegistry } from "@/components/module-registry-provider";
import { AssetCard } from "@/components/asset-card";
import { fetchTimelineAssets, fetchTimelineDays, fetchTimelineMonths, fetchTimelineYears } from "@/lib/api";
import { AssetSummary, TimelineDayBucket, TimelineMonthBucket, TimelineYearBucket } from "@/lib/types";

export default function TimelinePage() {
  const { getModule, loading: modulesLoading } = useModuleRegistry();
  const [years, setYears] = useState<TimelineYearBucket[]>([]);
  const [months, setMonths] = useState<TimelineMonthBucket[]>([]);
  const [days, setDays] = useState<TimelineDayBucket[]>([]);
  const [assets, setAssets] = useState<AssetSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [selectedMonth, setSelectedMonth] = useState<number | null>(null);
  const [selectedDay, setSelectedDay] = useState<number | null>(null);
  const timelineModule = getModule("timeline");
  const moduleActive = Boolean(timelineModule?.enabled && timelineModule.status === "active");

  useEffect(() => {
    if (!modulesLoading && moduleActive) {
      void loadYears();
    }
  }, [moduleActive, modulesLoading]);

  useEffect(() => {
    if (selectedYear) {
      void loadMonths(selectedYear);
      void loadAssets();
    } else {
      setMonths([]);
      setDays([]);
      setAssets([]);
    }
  }, [selectedYear]);

  useEffect(() => {
    if (selectedYear && selectedMonth) {
      void loadDays(selectedYear, selectedMonth);
      void loadAssets();
    } else {
      setDays([]);
    }
  }, [selectedMonth]);

  useEffect(() => {
    if (selectedYear || selectedMonth || selectedDay) {
       void loadAssets();
    }
  }, [selectedDay]);

  const loadYears = async () => {
    try {
      setError(null);
      const res = await fetchTimelineYears();
      setYears(res);
      if (res.length > 0) setSelectedYear(res[0].year);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to load timeline years.");
    }
  };

  const loadMonths = async (year: number) => {
    try {
      setError(null);
      const res = await fetchTimelineMonths(year);
      setMonths(res);
      setSelectedMonth(null);
      setSelectedDay(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to load timeline months.");
    }
  };

  const loadDays = async (year: number, month: number) => {
    try {
      setError(null);
      const res = await fetchTimelineDays(year, month);
      setDays(res);
      setSelectedDay(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to load timeline days.");
    }
  };

  const loadAssets = async () => {
    if (!selectedYear) return;
    setLoading(true);
    try {
      setError(null);
      const res = await fetchTimelineAssets(selectedYear, selectedMonth ?? undefined, selectedDay ?? undefined);
      setAssets(res.items);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to load timeline assets.");
    } finally {
      setLoading(false);
    }
  };

  if (modulesLoading) {
    return (
      <AppShell title="Timeline" description="Loading timeline module status.">
        <section className="panel empty-state">Checking timeline module…</section>
      </AppShell>
    );
  }

  if (!timelineModule) {
    return (
      <AppShell title="Timeline" description="Calendar-style browsing across indexed assets.">
        <section className="panel empty-state">
          <h2>Timeline module not installed</h2>
          <p className="subdued">This surface now comes from the built-in timeline module, but that module is not available in the registry.</p>
        </section>
      </AppShell>
    );
  }

  if (!moduleActive) {
    return (
      <AppShell title="Timeline" description="Calendar-style browsing across indexed assets.">
        <section className="panel empty-state">
          <h2>Timeline is unavailable</h2>
          <p className="subdued">{timelineModule.error ?? `Current status: ${timelineModule.status}.`}</p>
          {timelineModule.admin_mount ? (
            <p>
              <Link href={timelineModule.admin_mount} className="button small-button">Open Module Settings</Link>
            </p>
          ) : null}
        </section>
      </AppShell>
    );
  }

  return (
    <AppShell title="Timeline" description="Browse assets by creation date">
      {error ? <section className="panel empty-state">{error}</section> : null}
      <main className="timeline-container" style={{ padding: "1rem" }}>
        <div style={{ display: "flex", gap: "1rem", marginBottom: "2rem", flexWrap: "wrap" }}>
          <div className="timeline-col" style={{flex: 1}}>
            <h3>Years</h3>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              {years.map(({ year, count }) => (
                <button
                  key={year}
                  className={`button ${selectedYear === year ? "accent-button" : "subtle-button"}`}
                  onClick={() => setSelectedYear(year)}
                >
                  {year} ({count})
                </button>
              ))}
            </div>
          </div>
          
          {months.length > 0 && selectedYear && (
            <div className="timeline-col" style={{flex: 1}}>
              <h3>Months ({selectedYear})</h3>
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
                <button className={`button ${selectedMonth === null ? "accent-button" : "subtle-button"}`} onClick={() => setSelectedMonth(null)}>All</button>
                {months.map(({ month, count }) => (
                  <button
                    key={month}
                    className={`button ${selectedMonth === month ? "accent-button" : "subtle-button"}`}
                    onClick={() => setSelectedMonth(month)}
                  >
                    {month} ({count})
                  </button>
                ))}
              </div>
            </div>
          )}

          {days.length > 0 && selectedMonth && (
            <div className="timeline-col" style={{flex: 2}}>
              <h3>Days ({selectedYear}-{selectedMonth})</h3>
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
                <button className={`button ${selectedDay === null ? "accent-button" : "subtle-button"}`} onClick={() => setSelectedDay(null)}>All</button>
                {days.map(({ day, count }) => (
                  <button
                    key={day}
                    className={`button ${selectedDay === day ? "accent-button" : "subtle-button"}`}
                    onClick={() => setSelectedDay(day)}
                  >
                    {day} ({count})
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {loading ? (
          <div>Loading assets...</div>
        ) : (
          <div className="gallery-grid">
            {assets.map((asset) => (
              <AssetCard key={asset.id} asset={asset} />
            ))}
            {assets.length === 0 && <div className="subdued">No assets found for the selected timeframe.</div>}
          </div>
        )}
      </main>
    </AppShell>
  );
}
