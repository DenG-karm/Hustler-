import { describe, it, expect } from 'vitest'
import { parseProblemDetails, type ProblemDetails } from '../lib/problemDetails'

describe('K-703: RFC 7807 / RFC 9457 Problem Details Standardı Testleri', () => {
  it('Standart Problem Details nesnesini doğru ayrıştırmalıdır', () => {
    const rawProblem: ProblemDetails = {
      type: 'https://hustler.local/errors/slot-mismatch',
      title: 'Slot Uyuşmazlığı Hatası',
      status: 400,
      detail: 'slot_intro_video için gerekli dosya bulunamadı.',
      code: 'MISSING_SLOT',
      instance: '/api/v1/pipeline/assets',
    }

    const uiError = parseProblemDetails(rawProblem)

    expect(uiError.title).toBe('Slot Uyuşmazlığı Hatası')
    expect(uiError.message).toBe('slot_intro_video için gerekli dosya bulunamadı.')
    expect(uiError.code).toBe('MISSING_SLOT')
    expect(uiError.status).toBe(400)
    expect(uiError.mode).toBe('toast')
    expect(uiError.instance).toBe('/api/v1/pipeline/assets')
  })

  it('Kritik 500 ve ENCODER_FATAL hatalarını "modal" moduna eşlemelidir', () => {
    const criticalError: ProblemDetails = {
      type: 'https://hustler.local/errors/encoder-fatal',
      title: 'Donanım Kodlayıcı Hatası',
      status: 500,
      detail: 'NVENC aygıtı yanıt vermedi.',
      code: 'ENCODER_FATAL',
    }

    const uiError = parseProblemDetails(criticalError)

    expect(uiError.mode).toBe('modal')
    expect(uiError.title).toBe('Donanım Kodlayıcı Hatası')
    expect(uiError.status).toBe(500)
  })

  it('Ham stack trace veya Python traceback sızıntılarını sansürlemelidir (Sanitization)', () => {
    const rawTraceback = `Traceback (most recent call last):
      File "/app/services/core/hustler/main.py", line 42, in process_video
        raise RuntimeError("GPU memory exhausted at 0x7ffd98b")
      RuntimeError: GPU memory exhausted at 0x7ffd98b`

    const uiError = parseProblemDetails(rawTraceback)

    // Ham stack trace ve bellek adresleri kullanıcıya ASLA sızmamalı!
    expect(uiError.message).not.toContain('Traceback')
    expect(uiError.message).not.toContain('0x7ffd98b')
    expect(uiError.message).toContain('Sunucuda bir iç hata meydana geldi')
    expect(uiError.mode).toBe('toast')
  })

  it('Ham "500 Internal Server Error" metnini kullanıcı dostu mesaja dönüştürmelidir', () => {
    const raw500 = 'HTTP 500 Internal Server Error: unhandled crash'

    const uiError = parseProblemDetails(raw500)

    expect(uiError.message).not.toContain('Internal Server Error')
    expect(uiError.message).toContain('Sunucu işlemi tamamlayamadı')
    expect(uiError.mode).toBe('modal')
  })

  it('422 Doğrulama hatalarını "inline" moduna eşlemelidir', () => {
    const validationError: ProblemDetails = {
      type: 'https://hustler.local/errors/validation',
      title: 'Geçersiz İstek',
      status: 422,
      detail: 'Konu en az 3 karakter olmalıdır.',
      code: 'VALIDATION_FAILED',
    }

    const uiError = parseProblemDetails(validationError)

    expect(uiError.mode).toBe('inline')
    expect(uiError.message).toBe('Konu en az 3 karakter olmalıdır.')
  })
})
