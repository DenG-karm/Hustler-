import React, { useState } from 'react'
import { useFlowStore } from '../../../store/flowStore'
import { useTimerStore, formatDuration } from '../../../store/timerStore'
import { getIpcClient } from '../../../lib/ipc'
import { parseProblemDetails } from '../../../lib/problemDetails'

export const StatusBar: React.FC = () => {
  const connectionState = useFlowStore((s) => s.connectionState)
  const reconnectAttempt = useFlowStore((s) => s.reconnectAttempt)
  const addToast = useFlowStore((s) => s.addToast)

  // 15 Dakika SLA Kronometresi
  const elapsedSeconds = useTimerStore((s) => s.elapsedSeconds)
  const targetDurationSeconds = useTimerStore((s) => s.targetDurationSeconds)
  const slaStatus = useTimerStore((s) => s.slaStatus)

  // Tanılama Paketi İndirme Durumu
  const [isExportingDiag, setIsExportingDiag] = useState(false)

  const handleExportDiagnostics = async () => {
    setIsExportingDiag(true)
    try {
      const client = getIpcClient()
      if (typeof client.exportDiagnostics !== 'function') {
        throw new Error('Tanılama servisi istemcide mevcut değil')
      }
      const resp = await client.exportDiagnostics('json')
      if (resp.status >= 400) {
        const err = parseProblemDetails(resp)
        addToast({
          title: 'Tanılama Paketi Hatası',
          message: err.message,
          mode: 'toast',
          status: resp.status,
        })
      } else {
        const data = resp.body
        addToast({
          title: 'Tanılama Paketi Hazır (.zip)',
          message: `${data.filename} başarıyla oluşturuldu (${Math.round((data.size_bytes || 0) / 1024)} KB).\nKonum: ${data.bundle_path}`,
          mode: 'toast',
          code: 'DIAGNOSTICS_READY',
          status: 200,
        })
      }
    } catch (err: unknown) {
      const uiErr = parseProblemDetails(err)
      addToast({
        title: 'Tanılama Dışa Aktarılamadı',
        message: uiErr.message,
        mode: 'toast',
      })
    } finally {
      setIsExportingDiag(false)
    }
  }

  // SLA Durum Stilleri
  const slaColorMap = {
    ON_TRACK: 'text-success bg-success/10 border-success/25',
    WARNING: 'text-warning bg-warning/15 border-warning/35 animate-pulse',
    BREACHED: 'text-destructive bg-destructive/15 border-destructive/35 font-bold',
  }

  return (
    <footer
      className="h-9 w-full bg-surface border-t border-border/80 px-4 flex items-center justify-between text-[11px] select-none shrink-0 z-20"
      data-testid="studio-status-bar"
    >
      {/* SOL: Canlı Sidecar & SQLite Durumu */}
      <div className="flex items-center gap-3">
        {/* Sidecar Durum Göstergesi */}
        <div
          className="flex items-center gap-2 text-zinc-400"
          data-testid="status-pill-sidecar"
        >
          <span
            className={`w-2 h-2 rounded-full shrink-0 ${
              connectionState === 'connected'
                ? 'bg-emerald-400'
                : connectionState === 'connecting' || connectionState === 'reconnecting'
                ? 'bg-warning animate-ping'
                : 'bg-destructive'
            }`}
          />
          <span className="text-zinc-600 dark:text-zinc-300 font-medium">
            {connectionState === 'connected'
              ? 'Sidecar Çevrimiçi'
              : connectionState === 'connecting'
              ? 'Sidecar Bağlanıyor...'
              : connectionState === 'reconnecting'
              ? `Yeniden Bağlanılıyor (${reconnectAttempt})`
              : 'Sidecar Çevrimdışı'}
          </span>
        </div>

        <span className="hidden md:inline text-zinc-700">•</span>

        {/* SQLite WAL Bütünlük Hapı */}
        <div
          className="hidden md:flex items-center gap-1.5 text-zinc-500 dark:text-zinc-400 font-mono text-[10px]"
          data-testid="status-pill-sqlite"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-teal-400" />
          <span>SQLite: WAL</span>
        </div>

        <span className="hidden lg:inline text-zinc-700">•</span>

        {/* Zero-Network & Job Object Güvencesi */}
        <div className="hidden lg:flex items-center gap-1.5 text-zinc-500 font-mono text-[10px]">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
          <span>JobObject</span>
        </div>
      </div>

      {/* ORTA: 15 Dakika Üretim Kronometresi (SLA Tracker) */}
      <div className="flex items-center gap-2">
        <div
          className={`flex items-center gap-1.5 px-2 py-0.5 rounded border text-[10px] font-mono transition-colors ${slaColorMap[slaStatus]}`}
          data-testid="status-pill-timer"
          title={`Hedef: 15:00 (${Math.round((elapsedSeconds / targetDurationSeconds) * 100)}% tamamlandı)`}
        >
          <svg className="w-3 h-3 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
            <circle cx="12" cy="13" r="8" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4l2 2M9 2h6" />
          </svg>
          <span className="font-medium">{formatDuration(elapsedSeconds)}</span>
          <span className="text-zinc-500">/</span>
          <span className="text-zinc-500">{formatDuration(targetDurationSeconds)}</span>
          <span className="hidden sm:inline text-[10px] opacity-85">
            • {slaStatus === 'ON_TRACK' ? 'SLA Hedefinde' : slaStatus === 'WARNING' ? 'Eşik Uyarısı' : 'SLA İhlali'}
          </span>
        </div>
      </div>

      {/* SAĞ: Tanılama Paketi (.zip) İndir */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={handleExportDiagnostics}
          disabled={isExportingDiag}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[10px] font-mono font-medium bg-zinc-200/80 dark:bg-zinc-800/80 hover:bg-zinc-300/80 dark:hover:bg-zinc-700/80 text-zinc-700 dark:text-zinc-200 border border-border/80 transition-colors duration-150 disabled:opacity-50 cursor-pointer outline-none ring-0 focus:outline-none focus-visible:outline-none"
          title="Sistem sağlık raporu, sürümler ve oturum meta özetini içeren PII-maskelenmiş tanılama .zip paketini üretir"
          data-testid="btn-export-diagnostics"
        >
          {isExportingDiag ? (
            <>
              <svg className="w-3 h-3 animate-spin text-teal-400" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
              </svg>
              <span>Paketleniyor...</span>
            </>
          ) : (
            <>
              <svg className="w-3 h-3 text-teal-500 dark:text-teal-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              <span>Tanılama Paketi (.zip)</span>
            </>
          )}
        </button>
      </div>
    </footer>
  )
}
