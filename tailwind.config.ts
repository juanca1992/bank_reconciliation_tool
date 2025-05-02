
import type { Config } from "tailwindcss";
const { fontFamily } = require("tailwindcss/defaultTheme")

export default {
    darkMode: ["class"],
    content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
  	extend: {
      fontFamily: {
         sans: ["var(--font-inter)", ...fontFamily.sans], // Use Inter font
       },
  		colors: {
  			background: 'hsl(var(--background))',
  			foreground: 'hsl(var(--foreground))',
  			card: {
  				DEFAULT: 'hsl(var(--card))',
  				foreground: 'hsl(var(--card-foreground))'
  			},
  			popover: {
  				DEFAULT: 'hsl(var(--popover))',
  				foreground: 'hsl(var(--popover-foreground))'
  			},
  			primary: {
  				DEFAULT: 'hsl(var(--primary))', // Teal
  				foreground: 'hsl(var(--primary-foreground))' // White
  			},
  			secondary: {
  				DEFAULT: 'hsl(var(--secondary))', // Light Gray
  				foreground: 'hsl(var(--secondary-foreground))' // Dark text
  			},
  			muted: {
  				DEFAULT: 'hsl(var(--muted))', // Light Gray
  				foreground: 'hsl(var(--muted-foreground))' // Slightly darker gray text
  			},
  			accent: {
  				DEFAULT: 'hsl(var(--accent))', // Gold
  				foreground: 'hsl(var(--accent-foreground))' // Dark teal/black
  			},
  			destructive: {
  				DEFAULT: 'hsl(var(--destructive))',
  				foreground: 'hsl(var(--destructive-foreground))'
  			},
  			border: 'hsl(var(--border))',
  			input: 'hsl(var(--input))',
  			ring: 'hsl(var(--ring))', // Teal
  			chart: {
  				'1': 'hsl(var(--chart-1))',
  				'2': 'hsl(var(--chart-2))',
  				'3': 'hsl(var(--chart-3))',
  				'4': 'hsl(var(--chart-4))',
  				'5': 'hsl(var(--chart-5))'
  			},
  			sidebar: {
  				DEFAULT: 'hsl(var(--sidebar-background))', // Using default background for sidebar
  				foreground: 'hsl(var(--sidebar-foreground))', // Using default text
  				primary: 'hsl(var(--primary))', // Teal for primary sidebar elements
  				'primary-foreground': 'hsl(var(--primary-foreground))', // White
  				accent: 'hsl(var(--secondary))', // Light Gray for sidebar accents
  				'accent-foreground': 'hsl(var(--secondary-foreground))', // Dark text
  				border: 'hsl(var(--border))',
  				ring: 'hsl(var(--ring))' // Teal
  			}
  		},
  		borderRadius: {
  			lg: 'var(--radius)',
  			md: 'calc(var(--radius) - 2px)',
  			sm: 'calc(var(--radius) - 4px)'
  		},
  		keyframes: {
  			'accordion-down': {
  				from: {
  					height: '0'
  				},
  				to: {
  					height: 'var(--radix-accordion-content-height)'
  				}
  			},
  			'accordion-up': {
  				from: {
  					height: 'var(--radix-accordion-content-height)'
  				},
  				to: {
  					height: '0'
  				}
  			}
  		},
  		animation: {
  			'accordion-down': 'accordion-down 0.2s ease-out',
  			'accordion-up': 'accordion-up 0.2s ease-out'
  		}
  	}
  },
  plugins: [require("tailwindcss-animate")],
} satisfies Config;

