export interface GlobalViralPrototype {
  id: string
  format: 'short' | 'video'
  globalTitle: string
  globalUrl: string
  globalViewsFormatted: string
  retentionBadge: string
  durationText: string
  hookAnalysis: string
  prototypeTitle: string
  prototypeHook: string
  viralScore: number
  categoryLabel: string
}

const ytUrl = (q: string) => `https://www.youtube.com/results?search_query=${encodeURIComponent(q)}`

const p = (
  id: string,
  format: 'short' | 'video',
  globalTitle: string,
  q: string,
  views: string,
  ret: string,
  dur: string,
  hookAn: string,
  pTitle: string,
  pHook: string,
  score: number,
  cat: string
): GlobalViralPrototype => ({
  id,
  format,
  globalTitle,
  globalUrl: ytUrl(q),
  globalViewsFormatted: views,
  retentionBadge: ret,
  durationText: dur,
  hookAnalysis: hookAn,
  prototypeTitle: pTitle,
  prototypeHook: pHook,
  viralScore: score,
  categoryLabel: cat,
})

export function deriveGlobalViralPrototypes(
  channelName: string,
  channelDescription: string,
  _channelUrl: string,
  customIdeas?: { id: string; title: string; hook: string; score: number }[]
): GlobalViralPrototype[] {
  if (customIdeas && customIdeas.length > 0) {
    return customIdeas.map((idea, idx) => {
      const isShort = idx % 2 === 0
      const v = ((idx * 0.9) % 3 + 1.8).toFixed(1)
      return p(
        idea.id || `custom-${idx}`,
        isShort ? 'short' : 'video',
        idea.title,
        idea.title,
        `${v}M İzlenme`,
        isShort ? '%89 Tutunma' : '%68 Ortalama',
        isShort ? '0:45' : '13:20',
        idea.hook,
        idea.title,
        idea.hook,
        idea.score || 94,
        'Özel Niş Analizi'
      )
    })
  }

  const t = `${channelName} ${channelDescription}`.toLowerCase()

  if (t.includes('bilim') || t.includes('fizik') || t.includes('teknoloji') || t.includes('ai') || t.includes('uzay')) {
    return [
      p('sci-s1', 'short', 'Quantum Computing Will Break Modern Security', 'quantum computing chips shorts', '5.2M İzlenme', '%91 Tutunma', '0:42', 'Ters Köşe Kanca: Klasik çiplerin gelecekte neden yetersiz kalacağını ilk 3 saniyede açıklar.', `${channelName}: Kuantum Çipleri Normal Bilgisayarları Nasıl Geçecek?`, 'Kullandığınız işlemcinin güçlü olduğunu düşünüyorsanız, kuantum fiziğinin bu testine bakın.', 98, 'Viral Kanca'),
      p('sci-v1', 'video', 'James Webb Telescope Just Broke Cosmology Rules', 'james webb telescope mystery', '2.8M İzlenme', '%72 İzleme', '16:40', '3-Perde Belgesel Formatı: Standart modelin sınırları ve yeni derin uzay teleskop verileri.', `${channelName}: James Webb Standart Kozmolojiyi Nasıl Sarsıyor?`, 'Gökbilimciler bu fotoğrafa ilk baktıklarında ölçüm hatası sandılar; fakat bulgu çok daha büyüktü.', 93, 'Belgesel Kurgu'),
    ]
  }

  if (t.includes('para') || t.includes('finans') || t.includes('borsa') || t.includes('yatırım') || t.includes('girişim')) {
    return [
      p('fin-s1', 'short', 'The Brutal Truth About Morning Routines and Wealth', 'wealth habits morning routine shorts', '6.7M İzlenme', '%92 Tutunma', '0:39', 'Ezber Bozan Kanca: Yaygın klişelerin aksine sermaye birikiminin temel matematiği.', `${channelName}: Zenginlerin Sabah Rutinleri Hakkında 3 Büyük Yanılgı`, 'Sabah 5’te kalkmak tek başına zengin etmez; asıl farkı yaratan tek sermaye kuralı var.', 97, 'Viral Kanca'),
      p('fin-v1', 'video', 'How The Modern Financial System Actually Moves Money', 'how money works financial system', '3.4M İzlenme', '%74 İzleme', '18:50', 'Vaka İncelemesi: Borç döngüleri, faiz mekanizmaları ve küresel varlık transferleri.', `${channelName}: Küresel Para Sistemi ve Görünmeyen Finansal Çarklar`, 'Cüzdanınızdaki paranın alım gücü nasıl şekilleniyor? Merkez bankalarının perde arkası.', 94, 'Derin Analiz'),
    ]
  }

  return [
    p('gen-s1', 'short', 'The Most Effective Psychological Tactic in History', 'psychology persuasion tricks story', '7.8M İzlenme', '%95 Tutunma', '0:44', 'Merak Kancası: Tarihsel bir olayı beklenmedik psikolojik sonuçla harmanlar.', `${channelName}: Tarihte Kaydedilen En Zekice Psikolojik Hamle`, 'Bu taktik tek hamlede koca bir topluluğu etkiledi; yöntem tamamen algı yönetimiydi.', 99, 'Viral Kanca'),
    p('gen-v1', 'video', 'The Unsolved Mystery of Ancient Megaliths', 'ancient civilization engineering mystery', '3.6M İzlenme', '%76 İzleme', '17:20', 'Sürükleyici Anlatı: Arkeolojik keşiflerin mühendislik modellemeleriyle incelenmesi.', `${channelName}: Antik Mühendisliğin Bugün Bile Açıklanamayan 3 Sırrı`, 'Binlerce yıl önce inşa edilen bu yapılar modern yöntemlerle bile zor tekrarlanıyor.', 94, 'Belgesel Kurgu'),
  ]
}
