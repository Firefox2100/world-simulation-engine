import { createBrowserRouter } from "react-router-dom";
import { AppLayout } from "@/layouts/AppLayout";

export const router = createBrowserRouter([
    {
        path: "/",
        element: <AppLayout />,
        children: [
            {
                index: true,
                lazy: async () => ({
                    Component: (await import("@/pages/SimulationPage.jsx")).SimulationPage,
                }),
            },
            {
                path: "simulations/:simulationId",
                lazy: async () => ({
                    Component: (await import("@/pages/SimulationChatPage.jsx")).SimulationChatPage,
                }),
            },
            {
                path: "worlds",
                lazy: async () => ({
                    Component: (await import("@/pages/WorldPage.jsx")).WorldPage,
                }),
            },
            {
                path: "authors",
                lazy: async () => ({
                    Component: (await import("@/pages/AuthorsPage.jsx")).AuthorsPage,
                }),
            },
            {
                path: "media",
                lazy: async () => ({
                    Component: (await import("@/pages/MediaPage.jsx")).MediaPage,
                }),
            },
            {
                path: "connections",
                lazy: async () => ({
                    Component: (await import("@/pages/ConfigurationsPage.jsx")).ConfigurationsPage,
                }),
            },
            {
                path: "configurations",
                lazy: async () => ({
                    Component: (await import("@/pages/ConfigurationsPage.jsx")).ConfigurationsPage,
                }),
            },
        ],
    },
]);
