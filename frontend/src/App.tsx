import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './context/AuthContext';
import { NotificationProvider } from './context/NotificationContext';
import AppShell from './components/layout/AppShell';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import ProductsPage from './pages/ProductsPage';
import BatchesPage from './pages/BatchesPage';
import BatchDetailPage from './pages/BatchDetailPage';
import InspectionsPage from './pages/InspectionsPage';
import InspectionDetailPage from './pages/InspectionDetailPage';
import DefectsPage from './pages/DefectsPage';
import CAPAPage from './pages/CAPAPage';
import ReleaseGatesPage from './pages/ReleaseGatesPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 10000,
    },
  },
});

function MainRouter() {
  const { isAuthenticated, isLoading } = useAuth();

  // Navigation tab state
  const [activeTab, setActiveTab] = useState<string>('dashboard');

  // Detail drill-down states
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(null);
  const [selectedInspectionId, setSelectedInspectionId] = useState<string | null>(null);
  const [filterCapaDefectId, setFilterCapaDefectId] = useState<string | undefined>(undefined);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-3 border-sky-500 border-t-transparent rounded-full animate-spin"></div>
          <span className="text-sm font-semibold tracking-wider text-slate-300 uppercase">
            Initializing CastTrace AI...
          </span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  // Handle drilldowns
  const handleSelectBatch = (batchId: string) => {
    setSelectedBatchId(batchId);
    setActiveTab('batches');
  };

  const handleSelectInspection = (inspectionId: string) => {
    setSelectedInspectionId(inspectionId);
    setActiveTab('inspections');
  };

  const handleNavigateToCapa = (defectId?: string) => {
    setFilterCapaDefectId(defectId);
    setActiveTab('capa');
  };

  const handleTabChange = (tab: string) => {
    // Reset specific drill-downs when explicitly clicking navigation items
    if (tab !== 'batches') setSelectedBatchId(null);
    if (tab !== 'inspections') setSelectedInspectionId(null);
    if (tab !== 'capa') setFilterCapaDefectId(undefined);
    setActiveTab(tab);
  };

  return (
    <AppShell activeTab={activeTab} onTabChange={handleTabChange}>
      {activeTab === 'dashboard' && (
        <DashboardPage
          onNavigate={(target, id) => {
            if (target === 'batch' && id) {
              handleSelectBatch(id);
            } else if (target === 'inspection' && id) {
              handleSelectInspection(id);
            } else if (target === 'review') {
              setActiveTab('inspections');
            } else if (target === 'defect') {
              setActiveTab('defects');
            } else if (target === 'capa') {
              setActiveTab('capa');
            } else if (target === 'release-gates') {
              setActiveTab('release-gates');
            }
          }}
        />
      )}

      {activeTab === 'products' && (
        <ProductsPage
          onSelectProduct={() => {
            setActiveTab('batches');
          }}
        />
      )}

      {activeTab === 'batches' && (
        selectedBatchId ? (
          <BatchDetailPage
            batchId={selectedBatchId}
            onBack={() => setSelectedBatchId(null)}
            onNavigateToInspection={(insId) => handleSelectInspection(insId)}
            onNavigateToDefect={() => setActiveTab('defects')}
            onNavigateToCapa={(cId) => handleNavigateToCapa(cId)}
          />
        ) : (
          <BatchesPage onSelectBatch={handleSelectBatch} />
        )
      )}

      {activeTab === 'inspections' && (
        selectedInspectionId ? (
          <InspectionDetailPage
            inspectionId={selectedInspectionId}
            onBack={() => setSelectedInspectionId(null)}
            onNavigateToBatch={(bId) => handleSelectBatch(bId)}
            onNavigateToDefect={() => setActiveTab('defects')}
          />
        ) : (
          <InspectionsPage onSelectInspection={handleSelectInspection} />
        )
      )}

      {activeTab === 'defects' && (
        <DefectsPage
          onNavigateToCapa={(defId) => handleNavigateToCapa(defId)}
          onNavigateToBatch={(bId) => handleSelectBatch(bId)}
        />
      )}

      {activeTab === 'capa' && (
        <CAPAPage
          initialDefectId={filterCapaDefectId}
          onNavigateToDefect={() => setActiveTab('defects')}
        />
      )}

      {activeTab === 'release-gates' && (
        <ReleaseGatesPage
          onSelectBatch={handleSelectBatch}
          onNavigateToInspection={handleSelectInspection}
          onNavigateToDefect={() => setActiveTab('defects')}
          onNavigateToCapa={(cId) => handleNavigateToCapa(cId)}
        />
      )}
    </AppShell>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <NotificationProvider>
        <AuthProvider>
          <MainRouter />
        </AuthProvider>
      </NotificationProvider>
    </QueryClientProvider>
  );
}
