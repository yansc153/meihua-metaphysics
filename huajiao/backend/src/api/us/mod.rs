//! US market API handlers.

pub mod alpha_picks_portfolio;
pub mod citrini_chat;
pub mod citrini_reports;
pub mod discovery_full;
pub mod discovery_market;
pub mod discovery_today;
pub mod drawer;
pub mod ml_bars;
pub mod ml_bars_sync;
pub mod ml_pool;
pub mod ml_swing;
pub mod metaphysics;
pub mod review;

pub use metaphysics::{us_metaphysics_daily, us_metaphysics_question};
pub mod workbench;

pub use alpha_picks_portfolio::{alpha_picks_portfolio, AlphaPicksPortfolioRow};
pub use citrini_chat::{citrini_chat, load_citrini_chat_feed};
pub use citrini_reports::{citrini_reports, load_citrini_report_feed};
pub use discovery_full::us_discovery_full;
pub use discovery_market::us_discovery_market;
pub use discovery_today::us_discovery_today;
pub use drawer::us_drawer_stub;
pub use ml_bars::us_ml_bars;
pub use ml_pool::{
    init_hook_secret, merge_bar, ml_webhook_router, seed_base400, us_ml_base400, us_ml_pool,
};
pub use ml_swing::us_ml_swings;
pub use review::{build_pulse_aggregation, us_review};
pub use workbench::{
    load_magic_eye_feed, load_magic_eye_rows_for_symbols, load_quant_weekly_feed,
    magic_eye_new_entry, us_workbench, MAGIC_EYE_ROW_PROJECTION,
};
