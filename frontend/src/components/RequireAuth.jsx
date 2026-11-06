import { Navigate, useLocation } from "react-router-dom";
import { useAppData } from "../context/AppDataContext";

/**
 * Wraps a route so it's only reachable once signed in. Redirects to
 * /signin (preserving where the user was headed) otherwise.
 *
 * Waits for the initial GET /api/auth/me check to resolve before
 * deciding — without this, a signed-in user reloading the page would be
 * bounced to /signin for a flash of a frame while that request is
 * in-flight.
 */
function RequireAuth({ children }) {
  const { user, authChecked } = useAppData();
  const location = useLocation();

  if (!authChecked) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0B0D10] text-sm text-slate-500">
        Checking your session…
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/signin" replace state={{ from: location.pathname }} />;
  }

  return children;
}

export default RequireAuth;
