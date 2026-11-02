import axios from 'axios'
import { ElMessage } from 'element-plus'

import router from './router'

const TOKEN_KEY = 'matrix_token'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (token) => localStorage.setItem(TOKEN_KEY, token)
export const clearToken = () => localStorage.removeItem(TOKEN_KEY)

const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && router.currentRoute.value.name !== 'login') {
      clearToken()
      router.push({ name: 'login' })
    }
    const detail = error.response?.data?.detail
    ElMessage.error(typeof detail === 'string' ? detail : '请求失败')
    return Promise.reject(error)
  },
)

export default api
