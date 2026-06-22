import { createBrowserRouter } from "react-router-dom";
import { AppLayout } from "@/layouts/AppLayout";
import { ConnectionsPage } from "@/pages/ConnectionsPage.jsx";
import { SimulationChatPage } from "@/pages/SimulationChatPage.jsx";
import { SimulationPage } from "@/pages/SimulationPage.jsx";
import { WorldPage } from "@/pages/WorldPage.jsx";

export const router = createBrowserRouter([
    {
        path: "/",
        element: <AppLayout />,
        children: [
            { index: true, element: <SimulationPage /> },
            { path: "simulations/:simulationId", element: <SimulationChatPage /> },
            { path: "worlds", element: <WorldPage /> },
            { path: "connections", element: <ConnectionsPage /> },
        ],
    },
]);
