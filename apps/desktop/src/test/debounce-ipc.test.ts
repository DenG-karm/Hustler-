import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { debounce, createDebouncedScriptSaver } from '../lib/debounce'

describe('K-704: IPC Trafik Yönetimi & Debounce Mekanizması', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  describe('Minimum 400ms Kuralı ve Temel Debounce', () => {
    it('gecikme süresi 400ms altında verildiğinde 400ms olarak zorunlu kılınmalı ve uyarı vermelidir', () => {
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      const fn = vi.fn()

      const debounced = debounce(fn, 200) // 200ms < 400ms

      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining('minimum 400ms')
      )

      debounced('arg1')
      vi.advanceTimersByTime(350)
      expect(fn).not.toHaveBeenCalled() // 350ms geçti ama 400ms dolmadı

      vi.advanceTimersByTime(50) // toplam 400ms
      expect(fn).toHaveBeenCalledTimes(1)
      expect(fn).toHaveBeenCalledWith('arg1')
    })
  })

  describe('Hızlı Tuş Vuruşları ve IPC Çağrı Bastırma (Suppression)', () => {
    it('10 adet ardışık tuş vuruşunda IPC çağrısını sadece 1 keze indirgemeli ve 9 çağrıyı engellemelidir', async () => {
      const logs: string[] = []
      const logger = (msg: string) => logs.push(msg)
      const mockSaveIpc = vi.fn().mockResolvedValue({ status: 200 })

      const debouncedSaver = createDebouncedScriptSaver(mockSaveIpc, 400, logger)

      // Kullanıcının hızlıca metin yazdığını simüle et (10 tuş vuruşu)
      const textStates = [
        'H',
        'Hu',
        'Hus',
        'Hust',
        'Hustl',
        'Hustle',
        'Hustler',
        'Hustler ',
        'Hustler A',
        'Hustler AI',
      ]

      for (let i = 0; i < textStates.length; i++) {
        debouncedSaver('scr_1', 'Başlık', textStates[i])
        vi.advanceTimersByTime(15) // Her tuş vuruşu 15ms arayla
      }

      // Toplam 135ms geçti. Henüz debounce dolmadı (son vuruştan sonra 400ms beklenmeli)
      expect(mockSaveIpc).not.toHaveBeenCalled()

      // 300ms daha ilerlet (son vuruştan sonra ~300ms, toplam 435ms ama son vuruştan sonra 400ms dolmadı)
      vi.advanceTimersByTime(300)
      expect(mockSaveIpc).not.toHaveBeenCalled()

      // 100ms daha ilerlet (son vuruştan sonra 400ms doldu)
      vi.advanceTimersByTime(100)

      // Şimdi sadece 1 defa ve son argümanla IPC çağrısı yapılmış olmalıdır
      expect(mockSaveIpc).toHaveBeenCalledTimes(1)
      expect(mockSaveIpc).toHaveBeenCalledWith('scr_1', 'Başlık', 'Hustler AI')

      // Metrikleri doğrula
      const metrics = debouncedSaver.getMetrics()
      expect(metrics.totalInvocations).toBe(10)
      expect(metrics.totalExecutions).toBe(1)
      expect(metrics.suppressedCalls).toBe(9)

      // Logların başarıyla kaydedildiğini doğrula
      expect(logs.some((l) => l.includes('Toplam vuruş: 10'))).toBe(true)
      expect(logs.some((l) => l.includes('Engellenen gereksiz IPC çağrısı: 9'))).toBe(true)
    })

    it('kayıt tamamlandıktan sonra yeni yazma döngüsünde tekrar 400ms debounce uygulanmalıdır', async () => {
      const mockSaveIpc = vi.fn().mockResolvedValue({ status: 200 })
      const debouncedSaver = createDebouncedScriptSaver(mockSaveIpc, 400, () => {})

      // 1. Döngü
      debouncedSaver('scr_1', 'B1', 'İlk metin')
      debouncedSaver('scr_1', 'B1', 'İlk metin güncel')
      vi.advanceTimersByTime(400)
      expect(mockSaveIpc).toHaveBeenCalledTimes(1)

      // 2. Döngü: 1 saniye sonra kullanıcı tekrar yazmaya başladı
      vi.advanceTimersByTime(1000)
      debouncedSaver('scr_1', 'B1', 'İkinci tur metin 1')
      debouncedSaver('scr_1', 'B1', 'İkinci tur metin 2')
      debouncedSaver('scr_1', 'B1', 'İkinci tur metin son hali')

      vi.advanceTimersByTime(400)
      expect(mockSaveIpc).toHaveBeenCalledTimes(2)
      expect(mockSaveIpc).toHaveBeenLastCalledWith('scr_1', 'B1', 'İkinci tur metin son hali')

      const metrics = debouncedSaver.getMetrics()
      expect(metrics.totalInvocations).toBe(5)
      expect(metrics.totalExecutions).toBe(2)
      expect(metrics.suppressedCalls).toBe(3)
    })

    it('cancel() çağrıldığında bekleyen IPC çağrısı iptal edilmelidir', () => {
      const mockSaveIpc = vi.fn()
      const debouncedSaver = createDebouncedScriptSaver(mockSaveIpc, 400, () => {})

      debouncedSaver('scr_1', 'Başlık', 'Yazılan metin')
      expect(debouncedSaver.isPending()).toBe(true)

      debouncedSaver.cancel()
      expect(debouncedSaver.isPending()).toBe(false)

      vi.advanceTimersByTime(1000)
      expect(mockSaveIpc).not.toHaveBeenCalled()
    })

    it('flush() çağrıldığında 400ms beklenmeden derhal IPC çağrısı yapılmalıdır', () => {
      const mockSaveIpc = vi.fn()
      const debouncedSaver = createDebouncedScriptSaver(mockSaveIpc, 400, () => {})

      debouncedSaver('scr_1', 'Başlık', 'Acil kaydedilecek metin')
      expect(debouncedSaver.isPending()).toBe(true)

      debouncedSaver.flush()
      expect(mockSaveIpc).toHaveBeenCalledTimes(1)
      expect(mockSaveIpc).toHaveBeenCalledWith('scr_1', 'Başlık', 'Acil kaydedilecek metin')
      expect(debouncedSaver.isPending()).toBe(false)
    })
  })
})
