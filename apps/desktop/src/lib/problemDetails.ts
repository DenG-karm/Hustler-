/**
 * Hustler Desktop — Problem Details Standardı (RFC 7807 / RFC 9457)
 *
 * MİMARİ KURAL:
 * Backend'den gelen tüm hatalar standart Problem Details formatında ayrıştırılır (parse).
 * UI spesifik hata tiplerine (Toast, Modal, Inline) eşlenir.
 * Ham "500 Internal Server Error" veya teknik stack trace kullanıcıya ASLA yansıtılmaz.
 */

export interface ProblemDetails {
  type: string
  title: string
  status: number
  detail?: string
  instance?: string
  code?: string
  invalid_params?: Array<{ name: string; reason: string }>
}

export type ErrorDisplayMode = 'toast' | 'modal' | 'inline'

export interface UIError {
  id: string
  mode: ErrorDisplayMode
  title: string
  message: string
  code: string
  status: number
  instance?: string
  timestamp: number
  actionLabel?: string
  onAction?: () => void
}

/**
 * Backend'den veya IPC katmanından gelen hatayı standart UIError nesnesine eşler.
 */
export function parseProblemDetails(error: unknown): UIError {
  const timestamp = Date.now()
  const errorId = `err_${timestamp}_${Math.random().toString(36).substring(2, 7)}`

  // 1. Zaten ProblemDetails JSON formatında mı?
  if (typeof error === 'object' && error !== null) {
    const obj = error as any

    // Eğer IPC proxy yanıtıysa { status, body: { type, title, ... } }
    const problem: ProblemDetails = obj.body && typeof obj.body === 'object' && 'type' in obj.body
      ? obj.body
      : 'type' in obj
      ? obj
      : {
          type: 'https://hustler.local/errors/unknown',
          title: obj.title || obj.message || 'Beklenmeyen Sistem Hatası',
          status: typeof obj.status === 'number' ? obj.status : 500,
          detail: obj.detail || obj.message || 'İşlem gerçekleştirilirken bir hata oluştu.',
          code: obj.code || (obj.status ? `ERR_${obj.status}` : 'INTERNAL_ERROR'),
        }

    return mapToUIError(problem, errorId, timestamp)
  }

  // 2. Düz metin veya string hata
  const text = String(error || 'Bilinmeyen sistem hatası')

  // JSON dizesi mi?
  try {
    const parsed = JSON.parse(text)
    if (parsed && typeof parsed === 'object' && ('type' in parsed || 'detail' in parsed)) {
      return mapToUIError(
        {
          type: parsed.type || 'https://hustler.local/errors/parsed',
          title: parsed.title || 'İşlem Hatası',
          status: parsed.status || 500,
          detail: parsed.detail || parsed.message,
          code: parsed.code || 'PARSED_ERROR',
          instance: parsed.instance,
        },
        errorId,
        timestamp
      )
    }
  } catch {
    // Düz metin devam eder
  }

  // 3. Ham metin fallback'i (Teknik terimleri ve stack trace'i filtreler)
  const isFatal = text.toLowerCase().includes('500') || text.toLowerCase().includes('panic')
  const cleanMessage = sanitizeErrorMessage(text)

  return {
    id: errorId,
    mode: isFatal ? 'modal' : 'toast',
    title: isFatal ? 'Sunucu İşlem Hatası' : 'İşlem Uyarısı',
    message: cleanMessage,
    code: isFatal ? 'SERVER_ERROR' : 'OPERATION_FAILED',
    status: isFatal ? 500 : 400,
    timestamp,
  }
}

function mapToUIError(problem: ProblemDetails, id: string, timestamp: number): UIError {
  const status = problem.status || 500
  const isCritical = status >= 500 || problem.code === 'ENCODER_FATAL' || problem.code === 'JOB_ABORTED'

  // Mod belirleme: Kritik -> Modal, Doğrulama/İstemci -> Toast/Inline
  let mode: ErrorDisplayMode = 'toast'
  if (isCritical) {
    mode = 'modal'
  } else if (status === 422 || problem.code === 'VALIDATION_FAILED') {
    mode = 'inline'
  }

  const cleanDetail = sanitizeErrorMessage(problem.detail || problem.title)

  return {
    id,
    mode,
    title: problem.title || (isCritical ? 'Kritik Sistem Hatası' : 'İşlem Hatası'),
    message: cleanDetail,
    code: problem.code || `HTTP_${status}`,
    status,
    instance: problem.instance,
    timestamp,
  }
}

/**
 * Ham stack trace, python traceback veya bellek adreslerini temizler.
 */
function sanitizeErrorMessage(raw: string): string {
  if (!raw) return 'Ayrıntılı bilgi bulunmuyor.'
  // Traceback sızıntılarını kes
  if (raw.includes('Traceback (most recent call last)')) {
    return 'Sunucuda bir iç hata meydana geldi. Sistem yöneticisi günlüklere yönlendirildi.'
  }
  if (raw.includes('Internal Server Error')) {
    return 'Sunucu işlemi tamamlayamadı. Lütfen daha sonra tekrar deneyin.'
  }
  // Maksimum 200 karakterle sınırla
  return raw.length > 200 ? `${raw.substring(0, 197)}...` : raw
}
