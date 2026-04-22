import { CheckCircle, AlertCircle, Info, X } from 'lucide-react';
import type { Toast } from '../hooks/useToast';

interface Props {
  toasts: Toast[];
  removeToast: (id: string) => void;
}

const icons = {
  success: <CheckCircle size={15} />,
  error: <AlertCircle size={15} />,
  info: <Info size={15} />,
};

export default function ToastContainer({ toasts, removeToast }: Props) {
  return (
    <div className="toast-container">
      {toasts.map(t => (
        <div key={t.id} className={`toast toast-${t.type}`}>
          {icons[t.type]}
          <span style={{ flex: 1 }}>{t.message}</span>
          <button
            onClick={() => removeToast(t.id)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', padding: 0, display: 'flex' }}
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
