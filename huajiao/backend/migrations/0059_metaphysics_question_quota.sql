-- 0059: 问事配额。只有这一张新表。印价不在这里。
-- 另写入 meihua 的公开权利行：这是本服务自己算出的断语，不是付费上游正文。
-- 没有这行时 publication_gate 会一直把日频收成 unavailable。

CREATE TABLE IF NOT EXISTS metaphysics_question_quota (
    email text NOT NULL,
    day_shanghai date NOT NULL,
    used integer NOT NULL DEFAULT 0,
    PRIMARY KEY (email, day_shanghai)
);

INSERT INTO public.src_publication_rights (source, rights_state, reason)
VALUES ('meihua', 'pass', '玄学断语由本服务自算，不转发付费上游正文')
ON CONFLICT (source) DO NOTHING;
