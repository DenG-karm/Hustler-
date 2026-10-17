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
    } catch (err: any) {
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
    ON_TRACK: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    WARNING: 'text-amber-400 bg-amber-500/10 border-amber-500/30 animate-pulse',
    BREACHED: 'text-rose-400 bg-rose-500/10 border-rose-500/30 font-bold',
  }

  return (
    <footer
      className="h-9 w-full bg-surface/95 backdrop-blur-md border-t border-border/80 px-md flex items-center justify-between text-xs select-none shrink-0 z-20"
      data-testid="studio-status-bar"
    >
      {/* SOL: Canlı Sidecar & SQLite Durumu */}
      <div className="flex items-center gap-xs sm:gap-sm">
        {/* Sidecar Durum Hapı */}
        <div
          className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full border font-mono text-[11px] ${
            connectionState === 'connected'
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
              : connectionState === 'connecting'
              ? 'bg-amber-500/10 text-amber-400 border-amber-500/30 animate-pulse'
              : connectionState === 'reconnecting'
              ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
              : 'bg-rose-500/10 text-rose-400 border-rose-500/30'
          }`}
          data-testid="status-pill-sidecar"
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              connectionState === 'connected'
                ? 'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]'
                : connectionState === 'connecting' || connectionState === 'reconnecting'
                ? 'bg-amber-400 animate-ping'
                : 'bg-rose-400'
            }`}
          />
          <span>
            {connectionState === 'connected'
              ? 'Sidecar Çevrimiçi'
              : connectionState === 'connecting'
              ? 'Sidecar Bağlanıyor...'
              : connectionState === 'reconnecting'
              ? `Yeniden Bağlanılıyor (${reconnectAttempt})`
              : 'Sidecar Çevrimdışı'}
          </span>
        </div>

        {/* SQLite WAL Bütünlük Hapı */}
        <div
          className="hidden md:flex items-center gap-1.5 px-2 py-0.5 rounded-full border border-border/60 bg-surface-hover/60 text-text-secondary text-[11px] font-mono"
          data-testid="status-pill-sqlite"
          title="SQLite WAL (Write-Ahead Logging) Modu ve Bütünlük Denetimi Aktif"
        >
          <svg className="w-3 h-3 text-cyan-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <ellipse cx="12" cy="5" rx="9" ry="3" />
            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
          </svg>
          <span>SQLite: WAL Aktif</span>
        </div>

        {/* Zero-Network & Job Object Güvencesi */}
        <div
          className="hidden lg:flex items-center gap-1 px-2 py-0.5 rounded-full border border-border/40 text-text-muted text-[10px] font-mono"
          title="Windows Job Object ile yetim süreçler önlenir. Dış ağ çağrısı yasaktır."
        >
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-400/80" />
          <span>JobObject Korumalı</span>
        </div>
      </div>

      {/* ORTA: 15 Dakika Üretim Kronometresi (SLA Tracker) */}
      <div className="flex items-center gap-2">
        <div
          className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border text-[11px] font-mono transition-colors ${slaColorMap[slaStatus]}`}
          data-testid="status-pill-timer"
          title={`Hedef: 15:00 (${Math.round((elapsedSeconds / targetDurationSeconds) * 100)}% tamamlandı)`}
        >
          <span className="text-xs">⏱️</span>
          <span className="font-semibold">{formatDuration(elapsedSeconds)}</span>
          <span className="text-text-muted">/</span>
          <span className="text-text-muted">{formatDuration(targetDurationSeconds)}</span>
          <span className="hidden sm:inline text-[10px] opacity-80">
            • {slaStatus === 'ON_TRACK' ? 'SLA Hedefinde' : slaStatus === 'WARNING' ? 'Eşik Uyarısı' : 'SLA İhlali'}
          </span>
        </div>
      </div>

      {/* SAĞ: Tanılama Paketi (.zip) İndir & Log Kısayolu */}
      <div className="flex items-center gap-xs sm:gap-sm">
        <button
          type="button"
          onClick={handleExportDiagnostics}
          disabled={isExportingDiag}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium bg-primary/10 hover:bg-primary/20 text-primary border border-primary/30 transition-all duration-150 disabled:opacity-50 cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-primary"
          title="Sistem sağlık raporu, sürümler ve oturum meta özetini içeren PII-maskelenmiş tanılama .zip paketini üretir"
          data-testid="btn-export-diagnostics"
        >
          {isExportingDiag ? (
            <>
              <svg className="w-3.5 h-3.5 animate-spin text-primary" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
              </svg>
              <span>Paketleniyor...</span>
            </>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
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
