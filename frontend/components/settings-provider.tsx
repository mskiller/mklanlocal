"use client";

import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from "react";

type SettingsContextValue = {
  nsfwVisible: boolean;
  setNsfwVisible: (visible: boolean) => void;
};

const SettingsContext = createContext<SettingsContextValue | undefined>(undefined);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [nsfwVisible, setNsfwVisibleState] = useState<boolean>(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const stored = window.localStorage.getItem("media-indexer.nsfw-visible");
      if (stored === "true") {
        setNsfwVisibleState(true);
      }
    }
  }, []);

  const setNsfwVisible = (visible: boolean) => {
    setNsfwVisibleState(visible);
    if (typeof window !== "undefined") {
      window.localStorage.setItem("media-indexer.nsfw-visible", String(visible));
    }
  };

  const value = useMemo<SettingsContextValue>(
    () => ({
      nsfwVisible,
      setNsfwVisible,
    }),
    [nsfwVisible]
  );

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings() {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error("useSettings must be used inside SettingsProvider");
  }
  return context;
}
