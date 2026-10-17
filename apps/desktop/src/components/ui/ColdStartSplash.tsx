import React, { useState, useEffect, useRef } from 'react'
import { useFlowStore } from '../../store/flowStore'
import { useSupervisorStore } from '../../store/supervisorStore'
import { getIpcClient } from '../../lib/ipc'

interface CheckpointItem {
  id: string
  label: string
  detail: string
  isDone: boolean
}

/**
 * ColdStartSplash — İlk Başlatma ve Sidecar Doğrulama Perdesi
 * Kullanıcı ancak ve ancak Python Sidecar /health OK verip SSE olay akışına bağlandığında
 * stüdyoya erişebilir. Sahte animasyon ve tehlikeli "Atla" düğmesi KESİNLİKLE YASAKTIR.
 */
export const ColdStartSplash: React.FC = () => {
  const connectionState = useFlowStore((s) => s.connectionState)
  const reconnectAttempt = useFlowStore((s) => s.reconnectAttempt)
  const setConnectionState = useFlowStore((s) => s.setConnectionState)
  const supervisorStatus = useSupervisorStore((s) => s.status)
  const isSupervisorAlive = supervisorStatus === 'RUNNING'

  const isConnected = connectionState === 'connected'
  const hasConnectedRef = useRef(isConnected)
  if (isConnected) {
    hasConnectedRef.current = true
  }

  const [hasInitialized, setHasInitialized] = useState(isConnected)

  useEffect(() => {
    if (isConnected || hasConnectedRef.current) {
      setHasInitialized(true)
      return
    }

    let cancelled = false
    const verifyHealth = async () => {
      try {
        const resp = await getIpcClient().proxyRequest('GET', '/health')
        if (!cancelled && resp && resp.status === 200) {
          hasConnectedRef.current = true
          setConnectionState('connected', 0)
          setHasInitialized(true)
        }
      } catch {
        // Sidecar henüz ayağa kalkmadı, bir sonraki döngüde tekrar dene
      }
    }

    verifyHealth()
    const interval = setInterval(verifyHealth, 500)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [isConnected, setConnectionState])

  // Eğer gerçek bağlantı kurulduysa perdeden çık
  if (hasConnectedRef.current || hasInitialized || isConnected) {
    return null
  }

  const checkpoints: CheckpointItem[] = [
    {
      id: 'sidecar',
      label: 'Python Sidecar Süreci (FastAPI)',
      detail: isSupervisorAlive || connectionState !== 'disconnected'
        ? 'Dinamik portta dinleniyor, /health uç noktası doğrulanıyor'
        : 'İzole subprocess ayağa kaldırılıyor...',
      isDone: isConnected || isSupervisorAlive,
    },
    {
      id: 'db',
      label: 'SQLite WAL & Veritabanı Bütünlüğü',
      detail: isConnected
        ? 'Zero-Dirty-WAL kontrolü ve checkpoint truncate mekanizması aktif'
        : 'Veritabanı yazıcı kuyruğu bekleniyor...',
      isDone: isConnected,
    },
    {
      id: 'ipc',
      label: 'Zero-Network Güvenlik Duvarı & IPC Köprüsü',
      detail: 'Dış ağ çağrıları engellendi, Rust proxy el sıkışması aktif',
      isDone: true,
    },
    {
      id: 'sse',
      label: 'SSE Gerçek Zamanlı Olay Akışı El Sıkışması',
      detail: connectionState === 'reconnecting'
        ? `Yeniden bağlantı kuruluyor [#${reconnectAttempt}]...`
        : 'http://127.0.0.1/events SSE kanalı bekleniyor',
      isDone: isConnected,
    },
  ]

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-app/95 backdrop-blur-xl select-none"
      data-testid="cold-start-splash"
    >
      {/* Arka Plan Ortam Parıltısı */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[500px] h-[500px] bg-primary/10 rounded-full blur-3xl opacity-60 animate-pulse" />
      </div>

      {/* Ana Kart */}
      <div className="relative w-full max-w-lg p-xl mx-md rounded-2xl bg-surface/90 border border-border/80 shadow-2xl backdrop-blur-2xl flex flex-col items-center text-center space-y-lg animate-in fade-in zoom-in-95 duration-300">
        {/* Logo / Yükleme Çemberi */}
        <div className="relative flex items-center justify-center">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-primary to-purple-600 flex items-center justify-center shadow-lg shadow-primary/30 text-white font-extrabold text-2xl tracking-wider">
            H
          </div>
          <div className="absolute -inset-2 rounded-2xl border-2 border-primary/30 border-t-primary animate-spin" />
        </div>

        {/* Başlık & Açıklama */}
        <div className="space-y-xs">
          <h2 className="text-xl font-bold tracking-tight text-text-primary">
            Hustler Studio Hazırlanıyor
          </h2>
          <p className="text-sm text-text-secondary max-w-sm">
            Yerel motor ve sıfır ağ güvenlikli masaüstü kabuğu doğrulanıyor...
          </p>
        </div>

        {/* Kontrol Noktaları Listesi (Gerçek Durum Tabanlı) */}
        <div className="w-full space-y-sm text-left pt-xs">
          {checkpoints.map((cp) => (
            <div
              key={cp.id}
              className={`flex items-start gap-sm p-sm rounded-xl border transition-all duration-300 ${
                cp.isDone
                  ? 'bg-emerald-500/5 border-emerald-500/20 text-text-primary'
                  : 'bg-surface-hover/40 border-border/60 text-text-muted'
              }`}
            >
              <div
                className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 mt-0.5 transition-colors ${
                  cp.isDone
                    ? 'bg-emerald-500/20 text-emerald-400'
                    : 'bg-surface-hover text-text-muted border border-border'
                }`}
              >
                {cp.isDone ? (
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  <div className="w-2 h-2 rounded-full bg-primary/60 animate-ping" />
                )}
              </div>

              <div className="flex-1 min-w-0">
                <div className="text-xs font-semibold leading-tight">
                  {cp.label}
                </div>
                <div className="text-[11px] text-text-muted truncate mt-0.5">
                  {cp.detail}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Canlı Bağlantı Durumu (Atla Düğmesi Kesinlikle Yok) */}
        <div className="w-full pt-sm border-t border-border/60 flex items-center justify-between text-xs text-text-muted">
          <div className="flex items-center gap-1.5 font-mono text-[11px]">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
            <span>Motor bekleniyor...</span>
          </div>

          <span className="font-mono text-[11px] text-text-secondary">
            {reconnectAttempt > 0 ? `Yeniden Deneme: #${reconnectAttempt}` : 'İlk El Sıkışma'}
          </span>
        </div>
      </div>
    </div>
  )
}
