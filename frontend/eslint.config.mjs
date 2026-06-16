import coreWebVitals from "eslint-config-next/core-web-vitals";
import typescript from "eslint-config-next/typescript";

// eslint-config-next v16 ships native flat configs (see its `exports`),
// so we spread them directly rather than using the eslintrc compat bridge.
const eslintConfig = [
  ...coreWebVitals,
  ...typescript,
  {
    ignores: [".next/**", "node_modules/**"],
  },
];

export default eslintConfig;
