import resolve from '@rollup/plugin-node-resolve';
import typescript from '@rollup/plugin-typescript';
import terser from '@rollup/plugin-terser';
import css from 'rollup-plugin-import-css';

export default {
  input: 'src/panneau.ts',
  output: {
    file: '../custom_components/home_stock/panel/home-stock-panel.js',
    format: 'es',
    sourcemap: false,
  },
  plugins: [resolve(), typescript(), css({ inject: true }), terser()],
};
