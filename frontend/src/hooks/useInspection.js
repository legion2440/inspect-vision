import { useContext } from 'react';
import { InspectionContext } from '../context/InspectionProvider.jsx';

export function useInspection() {
  const ctx = useContext(InspectionContext);
  if (!ctx) throw new Error('useInspection must be used inside <InspectionProvider>');
  return ctx;
}
