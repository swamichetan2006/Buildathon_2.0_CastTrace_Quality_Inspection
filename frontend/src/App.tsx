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
import HealthPage from './pages/HealthPage';
import QualityIntelligencePage from './pages/QualityIntelligencePage';

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
  const [selectedDefectId, setSelectedDefectId] = useState<string | null>(null);
  const [filterCapaDefectId, setFilterCapaDefectId] = useState<string | undefined>(undefined);
  const [selectedCapaId, setSelectedCapaId] = useState<string | null>(null);
  const [selectedReleaseGateBatchId, setSelectedReleaseGateBatchId] = useState<string | null>(null);
  const [selectedBatchForIntelligence, setSelectedBatchForIntelligence] = useState<string | null>(null);
  const [intelligenceInitialView, setIntelligenceInitialView] = useState<'lot-summary' | 'attention' | 'recurrence'>('lot-summary');

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

  const handleSelectDefect = (defectId?: string) => {
    setSelectedDefectId(defectId || null);
    setActiveTab('defects');
  };

  const handleNavigateToCapa = (defectId?: string, capaId?: string) => {
    setFilterCapaDefectId(defectId);
    setSelectedCapaId(capaId || null);
    setActiveTab('capa');
  };

  const handleNavigateToReleaseGates = (batchId?: string) => {
    setSelectedReleaseGateBatchId(batchId || null);
    setActiveTab('release-gates');
  };

  const handleNavigateToIntelligence = (batchId?: string, initialView?: 'lot-summary' | 'attention' | 'recurrence') => {
    setSelectedBatchForIntelligence(batchId || null);
    if (initialView) setIntelligenceInitialView(initialView);
    setActiveTab('quality-intelligence');
  };

  const handleTabChange = (tab: string) => {
    // Reset specific drill-downs when explicitly clicking navigation items
    if (tab !== 'batches') setSelectedBatchId(null);
    if (tab !== 'inspections') setSelectedInspectionId(null);
    if (tab !== 'defects') setSelectedDefectId(null);
    if (tab !== 'capa') {
      setFilterCapaDefectId(undefined);
      setSelectedCapaId(null);
    }
    if (tab !== 'release-gates') setSelectedReleaseGateBatchId(null);
    if (tab !== 'quality-intelligence') {
      setSelectedBatchForIntelligence(null);
      setIntelligenceInitialView('lot-summary');
    }
    setActiveTab(tab);
  };

  return (
    <AppShell activeTab={activeTab} onTabChange={handleTabChange}>
      {activeTab === 'dashboard' && (
        <DashboardPage
          onNavigate={(target, id, extraId) => {
            if (target === 'batch' && id) {
              handleSelectBatch(id);
            } else if (target === 'inspection' && id) {
              handleSelectInspection(id);
            } else if (target === 'review') {
              setActiveTab('inspections');
            } else if (target === 'defect') {
              handleSelectDefect(id);
            } else if (target === 'capa') {
              handleNavigateToCapa(undefined, id);
            } else if (target === 'release-gates') {
              handleNavigateToReleaseGates(id);
            } else if (target === 'quality-intelligence') {
              handleNavigateToIntelligence(id, extraId as any);
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
            onNavigateToDefect={(dId) => handleSelectDefect(dId)}
            onNavigateToCapa={(cId) => handleNavigateToCapa(undefined, cId)}
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
            onNavigateToDefect={(dId) => handleSelectDefect(dId)}
          />
        ) : (
          <InspectionsPage onSelectInspection={handleSelectInspection} />
        )
      )}

      {activeTab === 'defects' && (
        <DefectsPage
          initialDefectId={selectedDefectId || undefined}
          onNavigateToCapa={(defId) => handleNavigateToCapa(defId)}
          onNavigateToBatch={(bId) => handleSelectBatch(bId)}
        />
      )}

      {activeTab === 'capa' && (
        <CAPAPage
          initialDefectId={filterCapaDefectId}
          initialCapaId={selectedCapaId || undefined}
          onNavigateToDefect={(dId) => handleSelectDefect(dId)}
        />
      )}

      {activeTab === 'release-gates' && (
        <ReleaseGatesPage
          initialBatchId={selectedReleaseGateBatchId || undefined}
          onSelectBatch={handleSelectBatch}
          onNavigateToInspection={handleSelectInspection}
          onNavigateToDefect={(dId) => handleSelectDefect(dId)}
          onNavigateToCapa={(cId) => handleNavigateToCapa(undefined, cId)}
        />
      )}

      {activeTab === 'quality-intelligence' && (
        <QualityIntelligencePage
          initialBatchId={selectedBatchForIntelligence}
          initialView={intelligenceInitialView}
          onNavigate={(target, id, extraId) => {
            if (target === 'batch' && id) {
              handleSelectBatch(id);
            } else if (target === 'inspection' && id) {
              handleSelectInspection(id);
            } else if (target === 'defect') {
              handleSelectDefect(id);
            } else if (target === 'capa') {
              handleNavigateToCapa(id, extraId);
            } else if (target === 'release-gates') {
              handleNavigateToReleaseGates(id);
            }
          }}
        />
      )}

      {activeTab === 'health' && <HealthPage />}
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
