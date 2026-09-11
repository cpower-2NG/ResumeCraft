import { chromium } from 'playwright'

const baseUrl = process.env.RESUME_WORKBENCH_URL || 'http://127.0.0.1:5173/'
const marker = Date.now()

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage()
const consoleErrors = []
page.on('console', message => {
  if (message.type() === 'error') consoleErrors.push(message.text())
})

try {
  await page.goto(baseUrl)
  await page.getByRole('heading', { name: '让经历沉淀为' }).waitFor()

  await page.getByRole('button', { name: /资料库/ }).click()
  await page.getByRole('heading', { name: '资料库' }).waitFor()
  await page.getByRole('button', { name: '新增资料' }).click()
  await page.getByRole('textbox', { name: /资料名称/ }).fill(`交互测试资料-${marker}`)
  await page.getByRole('button', { name: '保存资料' }).click()
  await page.getByText(`交互测试资料-${marker}`).waitFor()

  await page.getByRole('button', { name: 'R ResumeCraft' }).click()
  await page.getByRole('button', { name: /岗位画像/ }).click()
  await page.getByRole('button', { name: '新建岗位画像' }).click()
  await page.getByRole('textbox', { name: '画像名称' }).fill(`交互测试岗位-${marker}`)
  await page.getByRole('textbox', { name: '岗位方向' }).fill('交互测试')
  await page.getByRole('button', { name: '保存画像' }).click()
  await page.getByText(`交互测试岗位-${marker}`).waitFor()

  await page.getByRole('button', { name: 'R ResumeCraft' }).click()
  await page.getByRole('button', { name: /ResumeCraft/ }).click()
  await page.getByRole('heading', { name: '正式简历' }).waitFor()
  await page.getByRole('button', { name: '回收站' }).click()
  await page.getByRole('heading', { name: '简历回收站' }).waitFor()
  await page.getByRole('button', { name: '返回正式简历' }).click()
  await page.getByRole('heading', { name: '正式简历' }).waitFor()

  await page.getByRole('button', { name: 'R ResumeCraft' }).click()
  await page.getByRole('button', { name: /资料库/ }).click()
  await page.getByRole('button', { name: '回收站' }).click()
  await page.getByRole('heading', { name: '资料库' }).waitFor()
  await page.getByRole('button', { name: '返回资料库' }).waitFor()

  assert(consoleErrors.length === 0, `浏览器控制台出现错误: ${consoleErrors.join('; ')}`)
  console.log('interaction smoke test passed')
} finally {
  await browser.close()
}
