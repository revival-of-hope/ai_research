import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppShell } from "@/components/shell/app-shell";
import { ProtectedRoute } from "@/components/shell/protected-route";
import { AdminPage } from "@/pages/account/admin";
import { SettingsPage } from "@/pages/account/settings";
import { LoginPage } from "@/pages/public/login";
import { RegisterPage } from "@/pages/public/register";
import { GuidePage } from "@/pages/workspace/guide";
import { ComparisonPage } from "@/pages/workspace/comparison";
import { ResearchPage } from "@/pages/workspace/research";
import { SourcesPage } from "@/pages/workspace/sources";
import { UsagePage } from "@/pages/workspace/usage";


export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  {
    element: <ProtectedRoute />,
    children: [{
      element: <AppShell />,
      children: [
        { index: true, element: <Navigate to="/research" replace /> },
        { path: "research", element: <ResearchPage /> },
        { path: "comparison", element: <ComparisonPage /> },
        { path: "sources", element: <SourcesPage /> },
        { path: "usage", element: <UsagePage /> },
        { path: "settings", element: <SettingsPage /> },
        { path: "guide", element: <GuidePage /> },
        { path: "admin", element: <AdminPage /> },
      ],
    }],
  },
  { path: "*", element: <Navigate to="/research" replace /> },
]);
