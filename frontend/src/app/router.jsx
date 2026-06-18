import { createBrowserRouter } from "react-router-dom";
import { AppLayout } from "@/layouts/AppLayout";
import { SimulationPage } from "@/pages/SimulationPage.jsx";
import { WorldPage } from "@/pages/WorldPage.jsx";

export const router = createBrowserRouter([
    {
        path: "/",
        element: <AppLayout />,
        children: [
            { index: true, element: <SimulationPage /> },
            { path: "worlds", element: <WorldPage /> },
        ],
    },
]);
