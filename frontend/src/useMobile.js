import { onBeforeUnmount, ref } from 'vue'

// 手机宽度：导航收进抽屉、列表改卡片。和 CSS 里的 @media (max-width: 768px) 保持一致
const QUERY = '(max-width: 768px)'

export function useMobile() {
  const media = window.matchMedia(QUERY)
  const isMobile = ref(media.matches)
  const update = (e) => (isMobile.value = e.matches)
  media.addEventListener('change', update)
  onBeforeUnmount(() => media.removeEventListener('change', update))
  return isMobile
}
