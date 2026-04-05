<template>
  <div class="layout">
    <header class="topbar">
      <span class="logo">📖 Kindlemake</span>
      <nav>
        <RouterLink to="/crawl">Crawl</RouterLink>
        <RouterLink to="/jobs">Jobs</RouterLink>
        <RouterLink to="/library">Biblioteca</RouterLink>
      </nav>
    </header>
    <main class="main">
      <RouterView />
    </main>
  </div>
</template>
