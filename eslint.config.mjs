import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

const cfg = [
  // your existing Next.js presets
  ...compat.extends("next/core-web-vitals", "next/typescript"),

  // overrides to make unused-vars just warnings
  //
  // // .eslintrc.js

  {
    rules: {
      // JS/JSX
      "no-unused-vars": [
        "warn",
        {
          args: "none", // don’t warn on unused function args
          varsIgnorePattern: "^_", // allow `_foo`-prefixed names
        },
      ],
      // TS/TSX
      "@typescript-eslint/no-unused-vars": [
        "warn",
        {
          args: "none",
          varsIgnorePattern: "^_",
        },
      ],
    },
  },
];

export default cfg;
