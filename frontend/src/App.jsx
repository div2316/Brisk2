import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AppDataProvider } from "./context/AppDataContext";
import RequireAuth from "./components/RequireAuth";
import Welcome from "./pages/Welcome/Welcome";
import SignIn from "./pages/SignIn/SignIn";
import SignUp from "./pages/SignUp/SignUp";
import ForgotPassword from "./pages/ForgotPassword/ForgotPassword";
import ResetPassword from "./pages/ResetPassword/ResetPassword";
import Dashboard from "./pages/Dashboard/Dashboard";
import Assessment from "./pages/Assessment/Assessment";
import RiskAnalysis from "./pages/RiskAnalysis/RiskAnalysis";
import Report from "./pages/Report/Report";

const guard = (el) => <RequireAuth>{el}</RequireAuth>;

export default function App() {
  return (
    <AppDataProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Welcome />} />
          <Route path="/signin" element={<SignIn />} />
          <Route path="/signup" element={<SignUp />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/dashboard" element={guard(<Dashboard />)} />
          <Route path="/assessment" element={guard(<Assessment />)} />
          <Route path="/risk-analysis" element={guard(<RiskAnalysis />)} />
          <Route path="/report" element={guard(<Report />)} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AppDataProvider>
  );
}
