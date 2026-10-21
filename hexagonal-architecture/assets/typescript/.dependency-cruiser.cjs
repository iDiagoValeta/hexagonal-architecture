// dependency-cruiser template for a TypeScript repo with hexagonal architecture.
// Copy it to the root as .dependency-cruiser.cjs and run:
//   npx depcruise src --config .dependency-cruiser.cjs
//
// Adapt the paths if the core is not in src/core or the adapters are not
// in src/adapters. The rules are forbidden lists: if a dependency matches
// both "from" and "to", the command fails.

/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    {
      name: 'core-without-adapters',
      severity: 'error',
      comment: 'The core does not know adapters: the dependency points inward.',
      from: { path: '^src/core/' },
      to: { path: '^src/adapters/' },
    },
    {
      name: 'core-without-io',
      severity: 'error',
      comment:
        'The core does not import frameworks, ORMs, HTTP clients or Node IO modules. An npm package resolves to node_modules, so the path starts there.',
      from: { path: '^src/core/' },
      to: {
        path:
          '^node_modules/(pg|express|fastify|axios|mysql2|mongoose|prisma|typeorm)(/|$)|^node_modules/@prisma/client(/|$)|^node_modules/@aws-sdk(/|$)|^node:(fs|http|https|net|child_process)(/|$)|^(fs|http|https|net|child_process)(/|$)',
      },
    },
    {
      name: 'adapters-independent',
      severity: 'error',
      comment:
        'Two adapter families do not import each other. $1 is the group captured in from.path.',
      from: { path: '^src/adapters/(driving|driven)/' },
      to: { path: '^src/adapters/(?!$1)' },
    },

    // Uncomment this rule if each adapter lives in its own folder
    // (src/adapters/driven/postgres, src/adapters/driven/memory, etc.). The
    // group $1 becomes the adapter name and forbids imports between them,
    // not only between families.
    //
    // {
    //   name: 'adapters-isolated',
    //   severity: 'error',
    //   comment: 'Each adapter is independent from the others.',
    //   from: { path: '^src/adapters/(?:driving|driven)/([^/]+)/' },
    //   to: { path: '^src/adapters/(?:driving|driven)/(?!$1)' },
    // },
  ],

  options: {
    doNotFollow: { path: 'node_modules' },
    tsPreCompilationDeps: true,
  },
};
