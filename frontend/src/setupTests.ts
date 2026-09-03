// Matchers de DOM para o Vitest (`toBeInTheDocument`, `toHaveClass`, …).
// Roda em jsdom: nenhum navegador é aberto, então a ADR-008 ("testes sem rede e sem navegador")
// continua valendo — ver a emenda registrada na ADR-031.
import "@testing-library/jest-dom/vitest";
