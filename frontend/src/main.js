import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
// 放在 Element Plus 样式之后，覆盖它的变量
import './theme.css'

import App from './App.vue'
import router from './router'

createApp(App).use(ElementPlus, { locale: zhCn }).use(router).mount('#app')
