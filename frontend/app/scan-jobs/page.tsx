"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth-provider";
import { cancelScanJob, fetchScanJobs } from "@/lib/api";
import { ScanJob } from "@/lib/types";

export default function ScanJobsPage() {
  const { user } = useAuth();
  const [jobs, setJobs] = useState<ScanJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = async () => {
    try {
      setJobs(await fetchScanJobs());
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to load scan jobs.");
    }
  };

  useEffect(() => {
    void load();
    const interval = window.setInterval(() => {
      void load();
    }, 5000);
    return () => window.clearInterval(interval);
  }, []);

  return (
    <AppShell title="Scan Jobs" description="Track queue state, progress, and scan counters in near real time.">
      <section className="panel stack">
        {error ? <p className="subdued">{error}</p> : null}
        {message ? <p className="subdued">{message}</p> : null}
        {jobs.map((job) => (
          <article key={job.id} className="job-row">
            <div className="row-between">
              <div>
                <Link href={`/scan-jobs/${job.id}`} className="asset-name">
                  {job.id}
                </Link>
                <p className="subdued">{job.message ?? "Waiting for worker update."}</p>
              </div>
              <span className="pill">{job.status}</span>
            </div>
            <div className="progress-track">
              <div className="progress-bar" style={{ width: `${job.progress}%` }} />
            </div>
            <div className="metadata-grid">
              <div className="metadata-row">Scanned: {job.scanned_count}</div>
              <div className="metadata-row">New: {job.new_count}</div>
              <div className="metadata-row">Updated: {job.updated_count}</div>
              <div className="metadata-row">Deleted: {job.deleted_count}</div>
              <div className="metadata-row">Errors: {job.error_count}</div>
            </div>
            {user?.capabilities.can_run_scans && (job.status === "queued" || job.status === "running") ? (
              <div className="card-actions">
                <button
                  className="button ghost-button small-button"
                  type="button"
                  onClick={async () => {
                    setError(null);
                    setMessage(null);
                    try {
                      const cancelled = await cancelScanJob(job.id);
                      setMessage(`Cancelled scan job ${cancelled.id}.`);
                      await load();
                    } catch (nextError) {
                      setError(nextError instanceof Error ? nextError.message : "Unable to cancel scan job.");
                    }
                  }}
                >
                  Cancel Scan
                </button>
              </div>
            ) : null}
          </article>
        ))}
      </section>
    </AppShell>
  );
}
