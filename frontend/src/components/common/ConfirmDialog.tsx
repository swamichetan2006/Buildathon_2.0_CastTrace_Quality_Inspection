import React from 'react';
import { Modal } from './Modal';
import { Button } from './Button';
import { AlertTriangle, AlertCircle, Info } from 'lucide-react';

interface ConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  variant?: 'danger' | 'warning' | 'primary';
  isLoading?: boolean;
  loading?: boolean;
  children?: React.ReactNode;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmText = 'Confirm Action',
  cancelText = 'Cancel',
  variant = 'danger',
  isLoading = false,
  loading,
  children,
}) => {
  const isPending = isLoading || Boolean(loading);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title} maxWidth="md">
      <div className="space-y-4">
        <div className="flex items-start space-x-3.5">
          <div
            className={`p-2.5 rounded-xl flex-shrink-0 ${
              variant === 'danger'
                ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                : variant === 'warning'
                ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                : 'bg-teal-500/10 text-teal-400 border border-teal-500/20'
            }`}
          >
            {variant === 'danger' && <AlertCircle className="w-5 h-5" />}
            {variant === 'warning' && <AlertTriangle className="w-5 h-5" />}
            {variant === 'primary' && <Info className="w-5 h-5" />}
          </div>
          <p className="text-sm text-slate-300 leading-relaxed pt-0.5">{message}</p>
        </div>

        {children}

        <div className="flex items-center justify-end space-x-3 pt-4 border-t border-slate-800">
          <Button variant="ghost" onClick={onClose} disabled={isPending}>
            {cancelText}
          </Button>
          <Button variant={variant} onClick={onConfirm} isLoading={isPending}>
            {confirmText}
          </Button>
        </div>
      </div>
    </Modal>
  );
};

export default ConfirmDialog;
