"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";

export function AppShell({
  title,
  description,
  children,
  actions,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [navOpen, setNavOpen] = useState(false);
  const [desktopNavCollapsed, setDesktopNavCollapsed] = useState(false);

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, router, user]);

  useEffect(() => {
    setNavOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    setDesktopNavCollapsed(window.localStorage.getItem("media-indexer.desktop-nav-collapsed") === "true");
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem("media-indexer.desktop-nav-collapsed", String(desktopNavCollapsed));
  }, [desktopNavCollapsed]);

  useEffect(() => {
    if (!navOpen) {
      document.body.style.overflow = "";
      return;
    }
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, [navOpen]);

  if (loading || !user) {
    return (
      <main className="screen-center">
        <div className="panel soft-panel">
          <p className="eyebrow">Media Indexer</p>
          <h1>Checking session</h1>
        </div>
      </main>
    );
  }

  const navItems = [
    { href: "/", label: "Dashboard" },
    { href: "/sources", label: "Sources" },
    { href: "/browse-indexed", label: "Browse Indexed" },
    { href: "/search", label: "Search" },
    { href: "/collections", label: "Collections" },
    ...(user.capabilities.can_upload_assets ? [{ href: "/upload", label: "Upload" }] : []),
    { href: "/scan-jobs", label: "Scan Jobs" },
    ...(user.capabilities.can_view_admin ? [{ href: "/admin", label: "Admin" }] : []),
    { href: "/profile", label: "Profile" },
  ];
  const mobileItems = [
    { href: "/", label: "Home" },
    { href: "/sources", label: "Sources" },
    { href: "/browse-indexed", label: "Indexed" },
    { href: "/search", label: "Search" },
    { href: "/collections", label: "Collections" },
  ];

  const isActive = (href: string) => {
    if (href === "/") {
      return pathname === "/";
    }
    return pathname === href || pathname.startsWith(`${href}/`);
  };

  const handleLogout = async () => {
    await logout();
    router.replace("/login");
  };

  const accountActions = (
    <>
      <Link href="/profile" className="button ghost-button small-button">
        Profile
      </Link>
      <button className="button ghost-button small-button" type="button" onClick={() => void handleLogout()}>
        Sign Out
      </button>
    </>
  );

  return (
    <div className={`shell ${desktopNavCollapsed ? "shell-desktop-nav-collapsed" : ""} ${navOpen ? "shell-nav-open" : ""}`.trim()}>
      <div className="mobile-topbar">
        <button className="button ghost-button small-button mobile-nav-toggle" type="button" onClick={() => setNavOpen((value) => !value)}>
          {navOpen ? "Close" : "Menu"}
        </button>
        <div>
          <p className="eyebrow">Media Indexer</p>
          <p className="mobile-topbar-title">{title}</p>
        </div>
        <div className="mobile-topbar-actions">
          <span className="pill">{user.role}</span>
          <button className="button ghost-button small-button" type="button" onClick={() => void handleLogout()}>
            Sign Out
          </button>
        </div>
      </div>
      <button
        type="button"
        aria-label="Close navigation"
        className={`shell-scrim ${navOpen ? "shell-scrim-visible" : ""}`}
        onClick={() => setNavOpen(false)}
      />
      <button
        type="button"
        aria-label="Show navigation"
        className="button ghost-button small-button desktop-nav-reveal"
        onClick={() => setDesktopNavCollapsed(false)}
      >
        Show Menu
      </button>
      <aside className={`side-nav ${navOpen ? "side-nav-open" : ""}`}>
        <div className="stack">
          <div className="side-nav-header">
            <div className="side-nav-brand">
              <p className="eyebrow">Media Indexer</p>
              <h2>Approved Media</h2>
            </div>
            <button
              type="button"
              className="button ghost-button small-button desktop-nav-toggle"
              onClick={() => setDesktopNavCollapsed(true)}
            >
              Hide
            </button>
          </div>
          <div className="stack account-panel">
            <div>
              <p className="asset-name">{user.username}</p>
              <p className="subdued">Signed in as {user.role}</p>
            </div>
            <div className="card-actions">{accountActions}</div>
          </div>
        </div>
        <nav className="nav-list">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-link ${isActive(item.href) ? "nav-link-active" : ""}`}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="side-nav-spacer" aria-hidden="true" />
      </aside>
      <main className="content">
        <header className="page-header">
          <div>
            <p className="eyebrow">{user.username} · {user.role}</p>
            <h1>{title}</h1>
            {description ? <p className="subdued">{description}</p> : null}
          </div>
          <div className="page-actions">
            {actions}
            {accountActions}
          </div>
        </header>
        {children}
      </main>
      <nav className="mobile-bottom-nav">
        {mobileItems.map((item) => (
          <Link key={item.href} href={item.href} className={`mobile-bottom-link ${isActive(item.href) ? "mobile-bottom-link-active" : ""}`}>
            {item.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
