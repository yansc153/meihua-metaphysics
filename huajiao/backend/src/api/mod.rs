//! Axum API routes matching frontend page needs.

pub mod ashare;
pub mod auth;
pub mod common;
pub mod ops;
pub mod ranking_batch;
pub mod subscription;
pub mod upstream;
pub mod us;

pub use ashare::{
    a_share_auction, a_share_hot_money, a_share_mainline, a_share_review, a_share_sector_detail,
    a_share_sector_members, a_share_sectors, a_share_trading_calendar, a_share_window_open,
    a_share_workbench, build_a_share_tracking, compute_auction_window, drawer, find_workspace_root,
    kpl_ladder_staleness, kpl_staleness, lane_display_name, load_a_share_drawer,
    load_a_share_live_session, load_auction, load_hot_money, load_kpl_mood_snapshot,
    load_sector_detail, load_sector_members, load_sector_ranking, review_week_start,
    review_window_range, WorkbenchQuery,
};
pub use common::{envelope, publication_gate, ApiError, PublicationGate, ReviewQuery};
pub use us::{
    alpha_picks_portfolio, build_pulse_aggregation, citrini_chat, citrini_reports,
    load_citrini_chat_feed, load_citrini_report_feed, load_magic_eye_feed,
    load_magic_eye_rows_for_symbols, load_quant_weekly_feed, magic_eye_new_entry,
    us_discovery_full, us_discovery_market, us_discovery_today, us_ml_bars, us_ml_base400,
    us_ml_pool, us_ml_swings,     us_metaphysics_daily, us_metaphysics_question, us_review, us_workbench,
    MAGIC_EYE_ROW_PROJECTION,
};

use axum::{
    routing::{get, post},
    Router,
};
use sqlx::PgPool;

pub fn router() -> Router<PgPool> {
    Router::new()
        .route("/api/ashare/mainline", get(a_share_mainline))
        .route("/api/ashare/sectors", get(a_share_sectors))
        .route(
            "/api/ashare/sector/{plate_id}/members",
            get(a_share_sector_members),
        )
        .route(
            "/api/ashare/sector/{plate_id}/detail",
            get(a_share_sector_detail),
        )
        .route("/api/ashare/hot-money", get(a_share_hot_money))
        .route("/api/ashare/auction", get(a_share_auction))
        .route(
            "/api/ashare/trading-calendar",
            get(a_share_trading_calendar),
        )
        .route("/api/ashare/workbench", get(a_share_workbench))
        .route("/api/ashare/review", get(a_share_review))
        .route("/api/us/discovery/today", get(us_discovery_today))
        .route("/api/us/discovery/full", get(us_discovery_full))
        .route("/api/us/discovery/market", get(us_discovery_market))
        .route("/api/us/research/citrini/reports", get(citrini_reports))
        .route("/api/us/research/citrini/chat", get(citrini_chat))
        .route(
            "/api/us/research/pickalphas/alpha-picks-portfolio",
            get(alpha_picks_portfolio),
        )
        .route("/api/us/workbench", get(us_workbench))
        .route("/api/us/ml-pool", get(us_ml_pool))
        .route("/api/us/ml-400", get(us_ml_base400))
        .route("/api/us/ml-bars", get(us_ml_bars))
        .route("/api/us/ml-swings", get(us_ml_swings))
        .route("/api/us/review", get(us_review))
        .route("/api/us/metaphysics/daily", get(us_metaphysics_daily))
        .route("/api/us/metaphysics/question", post(us_metaphysics_question))
        .route("/api/drawer/{market}/{symbol}", get(drawer))
}
