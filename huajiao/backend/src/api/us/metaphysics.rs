//! 玄学网关。只做闸门、配额和转发。不计算卦。

use axum::extract::{Query, State};
use axum::http::HeaderMap;
use axum::Json;
use chrono::{FixedOffset, Utc};
use serde::Deserialize;
use serde_json::{json, Value};
use sqlx::PgPool;
use std::time::Duration;

use crate::api::auth::{session_token, token_hash};
use crate::api::common::envelope::envelope;
use crate::api::common::error::ApiError;
use crate::api::common::publication_gate::{publication_gate, PublicationGate};

const ALLOW: &[&str] = &[
    "QQQ", "XLK", "SMH", "DIA", "IWM", "XLC", "XLY", "XLF", "XLI", "XLB", "XLE", "XLV", "XLP",
    "XLRE", "XLU", "GLD", "SLV", "USO", "IBIT", "SPX",
];

#[derive(Deserialize)]
pub struct DailyQuery {
    session: Option<String>,
}

#[derive(Deserialize)]
pub struct QuestionBody {
    symbol: Option<String>,
    asked_at: Option<String>,
    note: Option<String>,
}

fn unavailable(reason: &str) -> Json<Value> {
    envelope("unavailable", json!([]), Some(reason), Some("meihua"))
}

fn meihua_url() -> String {
    std::env::var("MEIHUA_URL").unwrap_or_else(|_| "http://meihua:8090".to_string())
}

fn allowed(symbol: &str) -> bool {
    ALLOW.iter().any(|item| item.eq_ignore_ascii_case(symbol))
}

async fn caller_email(pool: &PgPool, headers: &HeaderMap) -> Result<String, ApiError> {
    let token = session_token(headers).ok_or_else(|| {
        ApiError::contract("metaphysics.session", "missing session")
    })?;
    let email: Option<String> = sqlx::query_scalar(
        "SELECT email FROM user_sessions WHERE token_hash = $1 AND revoked_at IS NULL AND expires_at > now()",
    )
    .bind(token_hash(&token))
    .fetch_optional(pool)
    .await
    .map_err(|error| ApiError::database("metaphysics.session", error))?;
    email.ok_or_else(|| ApiError::contract("metaphysics.session", "missing session"))
}

async fn post_meihua(path: &str, body: Value) -> Result<Value, ()> {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(3))
        .build()
        .map_err(|_| ())?;
    let response = client
        .post(format!("{}{path}", meihua_url()))
        .json(&body)
        .send()
        .await
        .map_err(|_| ())?;
    if !response.status().is_success() {
        return Err(());
    }
    response.json().await.map_err(|_| ())
}

fn complete_reading(value: &Value) -> bool {
    value.get("hexagram").and_then(Value::as_str).is_some_and(|text| !text.is_empty())
        && value.get("qishi_tier").and_then(Value::as_str).is_some()
        && value.get("phrase").and_then(Value::as_str).is_some()
}

pub async fn us_metaphysics_daily(
    State(pool): State<PgPool>,
    Query(query): Query<DailyQuery>,
) -> Result<Json<Value>, ApiError> {
    if let PublicationGate::Closed(shell) = publication_gate(&pool, "meihua", Some("meihua")).await?
    {
        return Ok(shell);
    }
    let symbols: Vec<&str> = ALLOW.iter().copied().filter(|symbol| *symbol != "SPX").collect();
    let mut body = json!({ "symbols": symbols });
    if let Some(session) = query.session.as_ref().filter(|text| !text.is_empty()) {
        body["session"] = json!(session);
    }
    match post_meihua("/v1/cast/daily", body).await {
        Ok(payload) if payload.get("index").and_then(|item| item.get("hexagram")).and_then(Value::as_str).is_some() => {
            Ok(Json(json!({
                "status": "ok",
                "source": "meihua",
                "freshness": "ok",
                "data": payload,
            })))
        }
        _ => Ok(unavailable("起卦服务不可用")),
    }
}

pub async fn us_metaphysics_question(
    State(pool): State<PgPool>,
    headers: HeaderMap,
    Json(body): Json<QuestionBody>,
) -> Result<Json<Value>, ApiError> {
    if let PublicationGate::Closed(shell) = publication_gate(&pool, "meihua", Some("meihua")).await?
    {
        return Ok(shell);
    }
    let symbol = body.symbol.unwrap_or_default();
    let asked_at = body.asked_at.unwrap_or_default();
    let note = body.note.unwrap_or_default();
    if symbol.trim().is_empty() || asked_at.trim().is_empty() || !allowed(symbol.trim()) {
        return Ok(unavailable("代码不在美股允许列表，或字段为空"));
    }
    let email = match caller_email(&pool, &headers).await {
        Ok(email) => email,
        Err(error) => return Err(error),
    };
    let shanghai = Utc::now().with_timezone(&FixedOffset::east_opt(8 * 3600).expect("offset"));
    let day = shanghai.date_naive();
    let mut tx = pool
        .begin()
        .await
        .map_err(|error| ApiError::database("metaphysics.quota", error))?;
    sqlx::query(
        "INSERT INTO metaphysics_question_quota (email, day_shanghai, used) VALUES ($1, $2, 0) ON CONFLICT DO NOTHING",
    )
    .bind(&email)
    .bind(day)
    .execute(&mut *tx)
    .await
    .map_err(|error| ApiError::database("metaphysics.quota", error))?;
    let used: i32 = sqlx::query_scalar(
        "SELECT used FROM metaphysics_question_quota WHERE email = $1 AND day_shanghai = $2 FOR UPDATE",
    )
    .bind(&email)
    .bind(day)
    .fetch_one(&mut *tx)
    .await
    .map_err(|error| ApiError::database("metaphysics.quota", error))?;
    if used >= 3 {
        tx.rollback().await.ok();
        return Ok(unavailable("今日问事已满 3 次"));
    }
    let reading = post_meihua(
        "/v1/cast/question",
        json!({ "symbol": symbol.trim(), "asked_at": asked_at, "note": note }),
    )
    .await;
    match reading {
        Ok(payload) if complete_reading(&payload) => {
            sqlx::query(
                "UPDATE metaphysics_question_quota SET used = used + 1 WHERE email = $1 AND day_shanghai = $2",
            )
            .bind(&email)
            .bind(day)
            .execute(&mut *tx)
            .await
            .map_err(|error| ApiError::database("metaphysics.quota", error))?;
            tx.commit()
                .await
                .map_err(|error| ApiError::database("metaphysics.quota", error))?;
            Ok(Json(json!({
                "status": "ok",
                "source": "meihua",
                "freshness": "ok",
                "data": payload,
            })))
        }
        _ => {
            tx.rollback().await.ok();
            Ok(unavailable("起卦服务不可用"))
        }
    }
}
