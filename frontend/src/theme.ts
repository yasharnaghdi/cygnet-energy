import { createTheme } from '@mantine/core'

export const theme = createTheme({
  primaryColor: 'teal',
  fontFamily: 'Inter, system-ui, sans-serif',
  defaultRadius: 'md',
  colors: {
    brand: [
      '#e6f7f7',
      '#b3e8e8',
      '#80d9d9',
      '#4dcaca',
      '#26bfbf',
      '#00b3b3',
      '#009999',
      '#007f7f',
      '#006666',
      '#004c4c',
    ],
  },
  components: {
    AppShell: {
      defaultProps: { padding: 'md' },
    },
  },
})
