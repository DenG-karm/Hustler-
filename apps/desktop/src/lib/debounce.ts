/**
 * Hustler Desktop — IPC Debounce & Trafik Kontrolü (K-704)
 *
 * MİMARİ KURAL: IPC TRAFİK YÖNETİMİ (Debounce)
 * Kullanıcı metin editöründe senaryoyu manuel düzenlerken her tuş vuruşunda (onChange)
 * Rust/FastAPI katmanına kayıt isteği atılmaz. UI katmanında minimum 400ms debounce
 * uygulanarak IPC trafiği kontrol altına alınır.
 */

export interface DebouncedFunction<T extends (...args: any[]) => any> {
  (...args: Parameters<T>): void
  cancel: () => void
  flush: () => void
  isPending: () => boolean
}

export interface DebounceMetrics {
  totalInvocations: number
  totalExecutions: number
  suppressedCalls: number
  lastExecutionTimestamp: number | null
}

/**
 * Genel amaçlı, minimum gecikme süreli debounce fonksiyonu.
 * Varsayılan gecikme: 400ms (K-704 gereksinimi).
 */
export function debounce<T extends (...args: any[]) => any>(
  fn: T,
  delayMs = 400
): DebouncedFunction<T> {
  if (delayMs < 400) {
    console.warn(`[Debounce Uyarı] Gecikme süresi (${delayMs}ms) K-704 standartı olan minimum 400ms'nin altındadır. 400ms olarak ayarlandı.`)
    delayMs = 400
  }

  let timerId: ReturnType<typeof setTimeout> | null = null
  let lastArgs: Parameters<T> | null = null

  const debounced = (...args: Parameters<T>) => {
    lastArgs = args
    if (timerId !== null) {
      clearTimeout(timerId)
    }

    timerId = setTimeout(() => {
      timerId = null
      if (lastArgs !== null) {
        const argsToCall = lastArgs
        lastArgs = null
        fn(...argsToCall)
      }
    }, delayMs)
  }

  debounced.cancel = () => {
    if (timerId !== null) {
      clearTimeout(timerId)
      timerId = null
    }
    lastArgs = null
  }

  debounced.flush = () => {
    if (timerId !== null && lastArgs !== null) {
      clearTimeout(timerId)
      timerId = null
      const argsToCall = lastArgs
      lastArgs = null
      fn(...argsToCall)
    }
  }

  debounced.isPending = () => timerId !== null

  return debounced
}

/**
 * K-704 Senaryo Kayıt IPC Trafik Yöneticisi.
 * Yapılan tuş vuruşlarını ve engellenen gereksiz IPC isteklerini metrik olarak kaydeder ve loglar.
 */
export function createDebouncedScriptSaver<T extends (...args: any[]) => Promise<any>>(
  saveFn: T,
  delayMs = 400,
  logger: (msg: string) => void = console.log
): DebouncedFunction<T> & { getMetrics: () => DebounceMetrics; resetMetrics: () => void } {
  let totalInvocations = 0
  let totalExecutions = 0
  let lastExecutionTimestamp: number | null = null

  const execute = async (...args: Parameters<T>) => {
    totalExecutions += 1
    lastExecutionTimestamp = Date.now()
    const suppressed = totalInvocations - totalExecutions
    logger(
      `[IPC Debounce] IPC kayıt isteği gönderildi (Tetiklenme #${totalInvocations}, Gerçek IPC Çağrısı #${totalExecutions}). Engellenen gereksiz IPC çağrısı: ${suppressed}`
    )
    await saveFn(...args)
  }

  const debounced = debounce((...args: Parameters<T>) => {
    void execute(...args)
  }, delayMs)

  const wrapped = (...args: Parameters<T>) => {
    totalInvocations += 1
    logger(
      `[IPC Debounce] Tuş vuruşu algılandı (Toplam vuruş: ${totalInvocations}). ${delayMs}ms debounce bekleniyor...`
    )
    debounced(...args)
  }

  wrapped.cancel = debounced.cancel
  wrapped.flush = debounced.flush
  wrapped.isPending = debounced.isPending

  wrapped.getMetrics = (): DebounceMetrics => ({
    totalInvocations,
    totalExecutions,
    suppressedCalls: Math.max(0, totalInvocations - totalExecutions),
    lastExecutionTimestamp,
  })

  wrapped.resetMetrics = () => {
    totalInvocations = 0
    totalExecutions = 0
    lastExecutionTimestamp = null
  }

  return wrapped
}
