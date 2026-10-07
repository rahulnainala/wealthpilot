#include "monte_carlo.h"

#include <algorithm>
#include <cmath>
#include <numeric>
#include <random>
#include <thread>

namespace wealthpilot::risk {

namespace {

constexpr double kMonthsPerYear = 12.0;

// Contribution weights: pro-rata to starting sleeve values, or equal when the
// sleeves start empty (a brand-new goal funded only by contributions).
std::vector<double> ContributionWeights(const std::vector<Sleeve>& sleeves) {
  std::vector<double> weights(sleeves.size(), 0.0);
  double total = 0.0;
  for (const auto& s : sleeves) total += s.value;

  if (total > 0.0) {
    for (std::size_t i = 0; i < sleeves.size(); ++i) weights[i] = sleeves[i].value / total;
  } else if (!sleeves.empty()) {
    std::fill(weights.begin(), weights.end(), 1.0 / static_cast<double>(sleeves.size()));
  }
  return weights;
}

// Read a per-month schedule: empty falls back to `fallback`, and a schedule
// shorter than the phase holds its last value (so "step up to X and stay there"
// needs only the months up to the step).
double ScheduleAt(const std::vector<double>& schedule, int month, double fallback) {
  if (schedule.empty()) return fallback;
  if (month < 0) return schedule.front();
  if (month < static_cast<int>(schedule.size())) return schedule[static_cast<std::size_t>(month)];
  return schedule.back();
}

// Simulate one path's ending value. Geometric Brownian motion per sleeve per
// month; contribution added after growth. No RNG draw when volatility is zero,
// so zero-vol paths are deterministic regardless of the seed.
double SimulateOnePath(const std::vector<Sleeve>& sleeves, const std::vector<double>& weights,
                       double contribution, int months, std::mt19937_64& rng) {
  std::normal_distribution<double> normal(0.0, 1.0);
  std::vector<double> values(sleeves.size());
  for (std::size_t i = 0; i < sleeves.size(); ++i) values[i] = sleeves[i].value;

  for (int m = 0; m < months; ++m) {
    for (std::size_t i = 0; i < sleeves.size(); ++i) {
      const double monthly_mean = sleeves[i].annual_return_mean / kMonthsPerYear;
      const double monthly_vol = sleeves[i].annual_return_volatility / std::sqrt(kMonthsPerYear);
      const double shock = monthly_vol > 0.0 ? normal(rng) : 0.0;
      const double growth =
          std::exp((monthly_mean - 0.5 * monthly_vol * monthly_vol) + monthly_vol * shock);
      values[i] = values[i] * growth + contribution * weights[i];
    }
  }
  return std::accumulate(values.begin(), values.end(), 0.0);
}

}  // namespace

double Percentile(const std::vector<double>& sorted, double q) {
  if (sorted.empty()) return 0.0;
  if (sorted.size() == 1) return sorted.front();
  const double rank = q * static_cast<double>(sorted.size() - 1);
  const auto lower = static_cast<std::size_t>(std::floor(rank));
  const auto upper = static_cast<std::size_t>(std::ceil(rank));
  const double frac = rank - static_cast<double>(lower);
  return sorted[lower] + frac * (sorted[upper] - sorted[lower]);
}

GoalSimResult RunGoalSimulation(const GoalSimInput& input) {
  const int paths = input.num_paths > 0 ? input.num_paths : kDefaultPaths;
  const int months = std::max(0, input.months_remaining);

  // Apply a one-time market shock at t=0, scaled by each sleeve's volatility
  // (equity sleeves take the full hit; near-cash barely moves).
  std::vector<Sleeve> sleeves = input.sleeves;
  if (input.initial_shock != 0.0) {
    constexpr double kEquityVol = 0.18;
    for (auto& s : sleeves) {
      const double beta = std::min(1.0, s.annual_return_volatility / kEquityVol);
      s.value = std::max(0.0, s.value * (1.0 + input.initial_shock * beta));
    }
  }
  const std::vector<double> weights = ContributionWeights(sleeves);

  const std::uint64_t base_seed = input.seed != 0 ? input.seed : std::random_device{}();

  std::vector<double> endings(static_cast<std::size_t>(paths), 0.0);

  auto worker = [&](int begin, int end) {
    for (int p = begin; p < end; ++p) {
      // Seed each path from (base_seed, path index) so results are independent
      // of how the work is partitioned across threads.
      std::seed_seq seq{static_cast<std::uint32_t>(base_seed & 0xffffffffULL),
                        static_cast<std::uint32_t>(base_seed >> 32), static_cast<std::uint32_t>(p)};
      std::mt19937_64 rng(seq);
      endings[static_cast<std::size_t>(p)] =
          SimulateOnePath(sleeves, weights, input.monthly_contribution, months, rng);
    }
  };

  unsigned hw = std::thread::hardware_concurrency();
  unsigned num_threads = std::max(1u, hw);
  if (paths < 1000) num_threads = 1;  // not worth the overhead for tiny runs

  if (num_threads == 1) {
    worker(0, paths);
  } else {
    std::vector<std::thread> threads;
    const int chunk = (paths + static_cast<int>(num_threads) - 1) / static_cast<int>(num_threads);
    for (unsigned t = 0; t < num_threads; ++t) {
      const int begin = static_cast<int>(t) * chunk;
      const int end = std::min(paths, begin + chunk);
      if (begin >= end) break;
      threads.emplace_back(worker, begin, end);
    }
    for (auto& th : threads) th.join();
  }

  const auto hits = static_cast<double>(std::count_if(
      endings.begin(), endings.end(), [&](double v) { return v >= input.target_value; }));

  std::sort(endings.begin(), endings.end());
  GoalSimResult result;
  result.probability_of_success = hits / static_cast<double>(paths);
  result.median_ending_value = Percentile(endings, 0.50);
  result.p10_value = Percentile(endings, 0.10);
  result.p90_value = Percentile(endings, 0.90);
  return result;
}

PortfolioRiskResult RunPortfolioRisk(const PortfolioRiskInput& input) {
  PortfolioRiskResult result;

  double total = 0.0;
  for (const auto& b : input.buckets) total += b.value;
  if (total <= 0.0 || input.buckets.empty()) return result;

  // Align series to the shortest available length.
  std::size_t periods = 0;
  bool first = true;
  for (const auto& b : input.buckets) {
    if (b.returns.empty()) continue;
    periods = first ? b.returns.size() : std::min(periods, b.returns.size());
    first = false;
  }
  if (periods == 0) return result;

  std::vector<double> weights(input.buckets.size());
  for (std::size_t i = 0; i < input.buckets.size(); ++i)
    weights[i] = input.buckets[i].value / total;

  // Portfolio return per period.
  std::vector<double> portfolio(periods, 0.0);
  for (std::size_t t = 0; t < periods; ++t) {
    double r = 0.0;
    for (std::size_t i = 0; i < input.buckets.size(); ++i) {
      if (t < input.buckets[i].returns.size()) r += weights[i] * input.buckets[i].returns[t];
    }
    portfolio[t] = r;
  }

  // Annualized volatility of the portfolio return series.
  {
    double mean = 0.0;
    for (double r : portfolio) mean += r;
    mean /= static_cast<double>(periods);
    double var_sum = 0.0;
    for (double r : portfolio) {
      const double d = r - mean;
      var_sum += d * d;
    }
    const double periodic_sd = std::sqrt(var_sum / static_cast<double>(periods));
    const double ppy = input.periods_per_year > 0.0 ? input.periods_per_year : 252.0;
    result.annual_volatility = periodic_sd * std::sqrt(ppy);
  }

  // Max drawdown: worst peak-to-trough of the cumulative wealth index.
  {
    double wealth = 1.0;
    double peak = 1.0;
    double max_dd = 0.0;
    for (double r : portfolio) {
      wealth *= 1.0 + r;
      peak = std::max(peak, wealth);
      if (peak > 0.0) max_dd = std::max(max_dd, 1.0 - wealth / peak);
    }
    result.max_drawdown = max_dd;
  }

  std::vector<double> sorted = portfolio;
  std::sort(sorted.begin(), sorted.end());
  const double alpha = 1.0 - input.confidence;  // e.g. 0.05
  const double q = Percentile(sorted, alpha);   // alpha-quantile return (a loss)

  // Tail scenarios: periods at or below the alpha-quantile.
  std::vector<std::size_t> tail;
  for (std::size_t t = 0; t < periods; ++t) {
    if (portfolio[t] <= q) tail.push_back(t);
  }
  if (tail.empty()) {  // interpolation edge — fall back to the single worst period
    const auto worst = std::min_element(portfolio.begin(), portfolio.end());
    tail.push_back(static_cast<std::size_t>(std::distance(portfolio.begin(), worst)));
  }

  double tail_mean = 0.0;
  for (std::size_t t : tail) tail_mean += portfolio[t];
  tail_mean /= static_cast<double>(tail.size());

  result.var = -q * total;
  result.cvar = -tail_mean * total;

  // Component CVaR: contribution_i = -mean(return_i over tail) * value_i.
  // These sum to CVaR by construction (an Euler allocation of the tail loss).
  for (std::size_t i = 0; i < input.buckets.size(); ++i) {
    double bucket_tail_mean = 0.0;
    for (std::size_t t : tail) {
      if (t < input.buckets[i].returns.size()) bucket_tail_mean += input.buckets[i].returns[t];
    }
    bucket_tail_mean /= static_cast<double>(tail.size());
    result.contributions.push_back(
        {input.buckets[i].bucket, -bucket_tail_mean * input.buckets[i].value});
  }
  return result;
}

std::vector<ProjectionBand> RunPortfolioProjection(const PortfolioProjectionInput& input) {
  const int paths = input.num_paths > 0 ? input.num_paths : kDefaultPaths;
  const int months = std::max(0, input.months);
  if (months == 0) return {};

  const std::vector<double> weights = ContributionWeights(input.sleeves);
  const std::uint64_t base_seed = input.seed != 0 ? input.seed : std::random_device{}();

  // monthly[m][p] = total portfolio value after month (m+1) on path p.
  std::vector<std::vector<double>> monthly(
      static_cast<std::size_t>(months), std::vector<double>(static_cast<std::size_t>(paths), 0.0));

  auto worker = [&](int begin, int end) {
    for (int p = begin; p < end; ++p) {
      std::seed_seq seq{static_cast<std::uint32_t>(base_seed & 0xffffffffULL),
                        static_cast<std::uint32_t>(base_seed >> 32), static_cast<std::uint32_t>(p)};
      std::mt19937_64 rng(seq);
      std::normal_distribution<double> normal(0.0, 1.0);

      std::vector<double> values(input.sleeves.size());
      for (std::size_t i = 0; i < input.sleeves.size(); ++i) values[i] = input.sleeves[i].value;

      for (int m = 0; m < months; ++m) {
        for (std::size_t i = 0; i < input.sleeves.size(); ++i) {
          const double monthly_mean = input.sleeves[i].annual_return_mean / kMonthsPerYear;
          const double monthly_vol =
              input.sleeves[i].annual_return_volatility / std::sqrt(kMonthsPerYear);
          const double shock = monthly_vol > 0.0 ? normal(rng) : 0.0;
          const double growth =
              std::exp((monthly_mean - 0.5 * monthly_vol * monthly_vol) + monthly_vol * shock);
          values[i] = values[i] * growth + input.monthly_contribution * weights[i];
        }
        monthly[static_cast<std::size_t>(m)][static_cast<std::size_t>(p)] =
            std::accumulate(values.begin(), values.end(), 0.0);
      }
    }
  };

  unsigned num_threads = std::max(1u, std::thread::hardware_concurrency());
  if (paths < 1000) num_threads = 1;
  if (num_threads == 1) {
    worker(0, paths);
  } else {
    std::vector<std::thread> threads;
    const int chunk = (paths + static_cast<int>(num_threads) - 1) / static_cast<int>(num_threads);
    for (unsigned t = 0; t < num_threads; ++t) {
      const int begin = static_cast<int>(t) * chunk;
      const int end = std::min(paths, begin + chunk);
      if (begin >= end) break;
      threads.emplace_back(worker, begin, end);
    }
    for (auto& th : threads) th.join();
  }

  std::vector<ProjectionBand> points;
  points.reserve(static_cast<std::size_t>(months));
  for (int m = 0; m < months; ++m) {
    std::vector<double>& col = monthly[static_cast<std::size_t>(m)];
    std::sort(col.begin(), col.end());
    points.push_back({m + 1, Percentile(col, 0.10), Percentile(col, 0.50), Percentile(col, 0.90)});
  }
  return points;
}

DiversificationResult RunDiversification(const std::vector<DivAsset>& assets) {
  DiversificationResult result;
  result.holdings = static_cast<int>(assets.size());
  if (assets.empty()) return result;

  const std::size_t n = assets.size();

  // Normalise weights; effective holdings = 1 / HHI.
  double wsum = 0.0;
  for (const auto& a : assets) wsum += a.weight;
  std::vector<double> w(n);
  for (std::size_t i = 0; i < n; ++i) {
    w[i] = wsum > 0.0 ? assets[i].weight / wsum : 1.0 / static_cast<double>(n);
  }
  double hhi = 0.0;
  for (double x : w) hhi += x * x;
  result.effective_holdings = hhi > 0.0 ? 1.0 / hhi : static_cast<double>(n);

  // Align return series to the shortest length.
  std::size_t periods = 0;
  bool first = true;
  for (const auto& a : assets) {
    if (a.returns.empty()) continue;
    periods = first ? a.returns.size() : std::min(periods, a.returns.size());
    first = false;
  }
  if (n < 2 || periods < 2) {
    result.diversification_ratio = 1.0;  // not enough data for correlations
    return result;
  }

  std::vector<double> mean(n, 0.0), sd(n, 0.0);
  for (std::size_t i = 0; i < n; ++i) {
    double m = 0.0;
    for (std::size_t t = 0; t < periods; ++t) m += assets[i].returns[t];
    m /= static_cast<double>(periods);
    mean[i] = m;
    double v = 0.0;
    for (std::size_t t = 0; t < periods; ++t) {
      const double d = assets[i].returns[t] - m;
      v += d * d;
    }
    sd[i] = std::sqrt(v / static_cast<double>(periods));
  }

  // Pairwise correlations: weighted-average correlation + candidate pairs.
  double weighted_corr = 0.0;
  double weight_pairs = 0.0;
  for (std::size_t i = 0; i < n; ++i) {
    for (std::size_t j = i + 1; j < n; ++j) {
      double cov = 0.0;
      for (std::size_t t = 0; t < periods; ++t) {
        cov += (assets[i].returns[t] - mean[i]) * (assets[j].returns[t] - mean[j]);
      }
      cov /= static_cast<double>(periods);
      const double denom = sd[i] * sd[j];
      const double corr = denom > 0.0 ? cov / denom : 0.0;
      const double pair_weight = w[i] * w[j];
      weighted_corr += pair_weight * corr;
      weight_pairs += pair_weight;
      result.top_pairs.push_back({assets[i].label, assets[j].label, corr});
    }
  }
  result.average_correlation = weight_pairs > 0.0 ? weighted_corr / weight_pairs : 0.0;

  // Diversification ratio = weighted-average vol / portfolio vol.
  std::vector<double> portfolio(periods, 0.0);
  double portfolio_mean = 0.0;
  for (std::size_t t = 0; t < periods; ++t) {
    double r = 0.0;
    for (std::size_t i = 0; i < n; ++i) r += w[i] * assets[i].returns[t];
    portfolio[t] = r;
    portfolio_mean += r;
  }
  portfolio_mean /= static_cast<double>(periods);
  double portfolio_var = 0.0;
  for (std::size_t t = 0; t < periods; ++t) {
    const double d = portfolio[t] - portfolio_mean;
    portfolio_var += d * d;
  }
  const double portfolio_sd = std::sqrt(portfolio_var / static_cast<double>(periods));
  double weighted_avg_vol = 0.0;
  for (std::size_t i = 0; i < n; ++i) weighted_avg_vol += w[i] * sd[i];
  result.diversification_ratio = portfolio_sd > 0.0 ? weighted_avg_vol / portfolio_sd : 1.0;

  std::sort(result.top_pairs.begin(), result.top_pairs.end(),
            [](const CorrPair& x, const CorrPair& y) { return x.correlation > y.correlation; });
  if (result.top_pairs.size() > 5) result.top_pairs.resize(5);
  return result;
}

RetirementPlanResult RunRetirementPlan(const RetirementPlanInput& input) {
  RetirementPlanResult result;

  const int paths = input.num_paths > 0 ? input.num_paths : kDefaultPaths;
  const int accum = std::max(0, input.accumulation_months);
  const int draw = std::max(0, input.drawdown_months);
  const int total_months = accum + draw;
  if (total_months == 0 || input.sleeves.empty()) return result;

  const std::vector<double> weights = ContributionWeights(input.sleeves);
  const std::uint64_t base_seed = input.seed != 0 ? input.seed : std::random_device{}();

  // Sample the fan yearly rather than monthly: 40+ years of monthly bands is a
  // lot of wire and pixels for a curve that moves smoothly. Month 0 (today) is
  // included so the chart starts at the real portfolio value.
  std::vector<int> band_months{0};
  for (int m = 12; m <= total_months; m += 12) band_months.push_back(m);
  if (band_months.back() != total_months) band_months.push_back(total_months);

  // banded[b][p] = total value at band_months[b] on path p.
  std::vector<std::vector<double>> banded(
      band_months.size(), std::vector<double>(static_cast<std::size_t>(paths), 0.0));
  std::vector<double> corpus_at_retirement(static_cast<std::size_t>(paths), 0.0);
  std::vector<double> terminal(static_cast<std::size_t>(paths), 0.0);
  std::vector<double> depletion_month(static_cast<std::size_t>(paths), -1.0);

  auto worker = [&](int begin, int end) {
    for (int p = begin; p < end; ++p) {
      std::seed_seq seq{static_cast<std::uint32_t>(base_seed & 0xffffffffULL),
                        static_cast<std::uint32_t>(base_seed >> 32), static_cast<std::uint32_t>(p)};
      std::mt19937_64 rng(seq);
      std::normal_distribution<double> normal(0.0, 1.0);

      std::vector<double> values(input.sleeves.size());
      for (std::size_t i = 0; i < input.sleeves.size(); ++i) values[i] = input.sleeves[i].value;

      std::size_t next_band = 0;
      auto record = [&](int month_done) {
        while (next_band < band_months.size() && band_months[next_band] == month_done) {
          banded[next_band][static_cast<std::size_t>(p)] =
              std::accumulate(values.begin(), values.end(), 0.0);
          ++next_band;
        }
      };
      record(0);
      // Retiring today: the corpus at the boundary is simply what's there now.
      if (accum == 0) {
        corpus_at_retirement[static_cast<std::size_t>(p)] =
            std::accumulate(values.begin(), values.end(), 0.0);
      }

      for (int m = 0; m < total_months; ++m) {
        const bool accumulating = m < accum;
        // Withdrawals come out pro-rata to each sleeve's *current* value, not
        // the starting weights — otherwise a drained sleeve keeps getting
        // charged and can go negative.
        double total_before = 0.0;
        if (!accumulating) total_before = std::accumulate(values.begin(), values.end(), 0.0);
        const double withdrawal =
            accumulating
                ? 0.0
                : std::min(total_before,
                           ScheduleAt(input.withdrawal_schedule, m - accum, 0.0));
        const double contribution =
            accumulating ? ScheduleAt(input.contribution_schedule, m, input.monthly_contribution)
                         : 0.0;

        for (std::size_t i = 0; i < input.sleeves.size(); ++i) {
          const double monthly_mean = input.sleeves[i].annual_return_mean / kMonthsPerYear;
          const double monthly_vol =
              input.sleeves[i].annual_return_volatility / std::sqrt(kMonthsPerYear);
          const double shock = monthly_vol > 0.0 ? normal(rng) : 0.0;
          const double growth =
              std::exp((monthly_mean - 0.5 * monthly_vol * monthly_vol) + monthly_vol * shock);
          const double share = total_before > 0.0 ? values[i] / total_before : weights[i];
          values[i] = values[i] * growth + contribution * weights[i] - withdrawal * share;
          if (values[i] < 0.0) values[i] = 0.0;
        }

        if (m + 1 == accum) {
          corpus_at_retirement[static_cast<std::size_t>(p)] =
              std::accumulate(values.begin(), values.end(), 0.0);
        }
        if (!accumulating && depletion_month[static_cast<std::size_t>(p)] < 0.0) {
          const double left = std::accumulate(values.begin(), values.end(), 0.0);
          // A corpus this small can't fund another month — call it depleted
          // rather than letting a rounding crumb compound back to life.
          if (left <= 1.0) {
            depletion_month[static_cast<std::size_t>(p)] = static_cast<double>(m - accum + 1);
          }
        }
        record(m + 1);
      }
      terminal[static_cast<std::size_t>(p)] = std::accumulate(values.begin(), values.end(), 0.0);
    }
  };

  unsigned num_threads = std::max(1u, std::thread::hardware_concurrency());
  if (paths < 1000) num_threads = 1;
  if (num_threads == 1) {
    worker(0, paths);
  } else {
    std::vector<std::thread> threads;
    const int chunk = (paths + static_cast<int>(num_threads) - 1) / static_cast<int>(num_threads);
    for (unsigned t = 0; t < num_threads; ++t) {
      const int begin = static_cast<int>(t) * chunk;
      const int end = std::min(paths, begin + chunk);
      if (begin >= end) break;
      threads.emplace_back(worker, begin, end);
    }
    for (auto& th : threads) th.join();
  }

  const auto hits = static_cast<double>(
      std::count_if(corpus_at_retirement.begin(), corpus_at_retirement.end(),
                    [&](double v) { return v >= input.target_value; }));
  result.probability_of_success = hits / static_cast<double>(paths);

  std::vector<double> sorted_corpus = corpus_at_retirement;
  std::sort(sorted_corpus.begin(), sorted_corpus.end());
  result.median_corpus = Percentile(sorted_corpus, 0.50);
  result.p10_corpus = Percentile(sorted_corpus, 0.10);
  result.p90_corpus = Percentile(sorted_corpus, 0.90);

  std::vector<double> sorted_terminal = terminal;
  std::sort(sorted_terminal.begin(), sorted_terminal.end());
  result.median_terminal_value = Percentile(sorted_terminal, 0.50);

  std::vector<double> depleted;
  for (double d : depletion_month) {
    if (d >= 0.0) depleted.push_back(d);
  }
  result.depletion_probability = static_cast<double>(depleted.size()) / static_cast<double>(paths);
  if (!depleted.empty()) {
    std::sort(depleted.begin(), depleted.end());
    result.median_depletion_month = Percentile(depleted, 0.50);
  }

  for (std::size_t b = 0; b < band_months.size(); ++b) {
    std::sort(banded[b].begin(), banded[b].end());
    ProjectionBand band;
    band.month = band_months[b];
    band.p10 = Percentile(banded[b], 0.10);
    band.median = Percentile(banded[b], 0.50);
    band.p90 = Percentile(banded[b], 0.90);
    result.bands.push_back(band);
  }
  return result;
}

}  // namespace wealthpilot::risk
