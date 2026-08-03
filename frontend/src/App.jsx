import { RouterProvider, createRouter } from '@tanstack/react-router';
import { routeTree } from './routeTree.gen';
import { InspectionProvider } from './context/InspectionProvider.jsx';

const router = createRouter({ routeTree, defaultPreload: 'intent' });

export default function App() {
  return (
    <InspectionProvider>
      <RouterProvider router={router} />
    </InspectionProvider>
  );
}
