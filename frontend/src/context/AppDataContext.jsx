import { createContext, useContext, useEffect, useState, useCallback } from "react";
import {
  apiSignUp, apiSignIn, apiSignOut, apiCurrentUser,
  apiGetPatient, apiAssessments, apiReliability, predictRisk,
} from "../lib/api";

const AppDataContext = createContext(null);

export function AppDataProvider({ children }) {
  const [user, setUser] = useState(null);
  const [latest, setLatest] = useState(null); // {id, created_at, patient, prediction}
  const [history, setHistory] = useState([]);
  const [reliability, setReliability] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [l, h, r] = await Promise.all([apiGetPatient(), apiAssessments(), apiReliability().catch(() => null)]);
      setReliability(r);
      setLatest(l?.prediction ? l : null);
      setHistory(h?.items || []);
    } catch {
      setLatest(null);
      setHistory([]);
      setReliability(null);
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const { user: me } = await apiCurrentUser();
        if (me) { setUser(me); await refresh(); }
      } catch {
        setUser(null);
      } finally {
        setAuthChecked(true);
      }
    })();
  }, [refresh]);

  const signUp = useCallback(async ({ name, email, password, acceptTerms }) => {
    try { await apiSignUp({ name, email, password, acceptTerms }); return { ok: true }; }
    catch (err) { return { ok: false, error: err.message }; }
  }, []);

  const signIn = useCallback(async ({ email, password }) => {
    try {
      const { user: me } = await apiSignIn({ email, password });
      setUser(me);
      await refresh();
      return { ok: true };
    } catch (err) { return { ok: false, error: err.message }; }
  }, [refresh]);

  const signOut = useCallback(async () => {
    try { await apiSignOut(); } catch { /* ignore */ }
    setUser(null); setLatest(null); setHistory([]); setReliability(null);
  }, []);

  // Runs the model, stores the result in the database, refreshes state.
  const runAssessment = useCallback(async (record) => {
    const res = await predictRisk(record);
    await refresh();
    return res;
  }, [refresh]);

  const value = { user, latest, history, reliability, authChecked, signUp, signIn, signOut, runAssessment, refresh };
  return <AppDataContext.Provider value={value}>{children}</AppDataContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAppData() {
  const ctx = useContext(AppDataContext);
  if (!ctx) throw new Error("useAppData must be used within an AppDataProvider");
  return ctx;
}
