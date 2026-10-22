import React from 'react';
import clsx from 'clsx';
import {
  ShieldAlert,
  CheckCircle2,
  Clock,
  AlertTriangle,
  XCircle,
  PauseCircle,
  FileSearch,
  Sparkles,
} from 'lucide-react';

interface BadgeProps {
  variant?:
    | 'success'
    | 'danger'
    | 'warning'
    | 'info'
    | 'neutral'
    | 'purple'
    | 'amber'
    | 'teal';
  size?: 'sm' | 'md';
  children?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
  status?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  variant = 'neutral',
  size = 'md',
  children,
  icon,
  className,
  status,
}) => {
  if (status) {
    return <StatusBadge status={status} size={size} />;
  }
  const variantStyles = {
    success: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    danger: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    warning: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    info: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
    neutral: 'bg-slate-700/30 text-slate-300 border-slate-600/40',
    purple: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
    amber: 'bg-amber-600/20 text-amber-200 border-amber-500/40',
    teal: 'bg-teal-500/15 text-teal-300 border-teal-500/30',
  };

  const sizeStyles = {
    sm: 'text-[10px] px-2 py-0.5 space-x-1',
    md: 'text-xs px-2.5 py-1 space-x-1.5',
  };

  return (
    <span
      className={clsx(
        'inline-flex items-center font-medium rounded-full border shadow-xs tracking-wide uppercase font-mono',
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
    >
      {icon && <span className="flex-shrink-0">{icon}</span>}
      <span>{children}</span>
    </span>
  );
};

export const StatusBadge: React.FC<{ status: string; size?: 'sm' | 'md' }> = ({ status, size = 'md' }) => {
  switch (status) {
    case 'RELEASED':
    case 'COMPLETED':
    case 'RESOLVED':
    case 'VERIFIED':
    case 'CLEAR':
    case 'CONFIRMED_GOOD':
    case 'SUCCEEDED':
    case 'DEFECT_RESOLVED':
    case 'LIKELY_OK':
      return (
        <Badge variant="success" size={size} icon={<CheckCircle2 className="w-3 h-3" />}>
          {status.replace(/_/g, ' ')}
        </Badge>
      );

    case 'ON_HOLD':
    case 'HOLD':
      return (
        <Badge variant="amber" size={size} icon={<PauseCircle className="w-3 h-3" />}>
          ON HOLD
        </Badge>
      );

    case 'CRITICAL':
    case 'CONFIRMED_DEFECTIVE':
    case 'DEFECTIVE':
    case 'FAILED':
    case 'REJECTED':
    case 'REOPENED':
    case 'SCRAPPED':
    case 'REJECT_SCRAP':
    case 'LIKELY_DEFECTIVE':
      return (
        <Badge variant="danger" size={size} icon={<ShieldAlert className="w-3 h-3" />}>
          {status.replace(/_/g, ' ')}
        </Badge>
      );

    case 'MAJOR':
    case 'DISPUTED':
    case 'NEEDS_REVIEW':
    case 'AI_FLAGGED':
    case 'ACTION_ASSIGNED':
    case 'DEFECT_RECURRED_REOPENED':
      return (
        <Badge variant="warning" size={size} icon={<AlertTriangle className="w-3 h-3" />}>
          {status.replace(/_/g, ' ')}
        </Badge>
      );

    case 'PENDING':
    case 'IN_PROGRESS':
    case 'IN_REVIEW':
    case 'QUEUED':
    case 'PROCESSING':
    case 'PENDING_REINSPECTION':
      return (
        <Badge variant="info" size={size} icon={<Clock className="w-3 h-3" />}>
          {status.replace(/_/g, ' ')}
        </Badge>
      );

    case 'DRAFT':
    case 'SUBMITTED':
      return (
        <Badge variant="neutral" size={size} icon={<FileSearch className="w-3 h-3" />}>
          {status.replace(/_/g, ' ')}
        </Badge>
      );

    case 'CONCESSION_DEVIATION':
    case 'CONCESSION':
      return (
        <Badge variant="purple" size={size} icon={<Sparkles className="w-3 h-3" />}>
          CONCESSION
        </Badge>
      );

    case 'CANCELLED':
    case 'ARCHIVED':
      return (
        <Badge variant="neutral" size={size} icon={<XCircle className="w-3 h-3" />}>
          {status.replace(/_/g, ' ')}
        </Badge>
      );

    default:
      return (
        <Badge variant="neutral" size={size}>
          {status.replace(/_/g, ' ')}
        </Badge>
      );
  }
};

export default Badge;
