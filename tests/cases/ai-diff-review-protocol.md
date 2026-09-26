# ai-diff-review-protocol

## Case 1: 要求改一处，diff 里夹带了重构

**输入 / Input**

请求是"修复登录页的空指针"。diff 改了 14 个文件、增 620 行删 380 行，
其中包含把日志库从 A 换成 B、重命名了三个公共方法、以及那处真正的空指针修复。

**期望 / Expected**

- [ ] Step 1 意图匹配判为不匹配：夹带的重构远大于请求范围
- [ ] 决策为 `stop`，理由写"hidden scope creep dominates the patch"
- [ ] 先跑 `scripts/diff_risk.py`（拿不到可运行的环境时按正文同一张阈值表手数，并标 "counted by hand"），
      Diff stats 一段写出 14 个文件、+620/−380，指出越过"9 个文件以上"和"200 行以上"两条阈值，
      并写明必须人工逐段过全部 hunk
- [ ] 给出可执行的下一步：把修复与重构拆成两个 diff
- [ ] 不逐行精读，只点出高风险位置

**反例 / Must not**

- 不得因为"重构本身是好事"就放行
- 不得逐行复述 diff 内容

## Case 2: 改动很小，但动了迁移文件

**输入 / Input**

`tests/fixtures/ai-diff-review-protocol/add-age-not-null.diff`：只改了 2 个文件、增 11 行，
其中一个是新加的数据库迁移脚本，`ALTER TABLE users ADD COLUMN age integer NOT NULL;`，没有默认值。请求是"注册表单要存年龄"。

**期望 / Expected**

- [ ] `diff_risk.py` 的 Diff stats 写出 2 个文件、+11/−0，报出 `migration` 边界和
      `not-null-without-default`（迁移文件第 3 行），并写明必须人工逐段过那一段
- [ ] Step 2 边界安全命中：迁移文件属于高风险边界
- [ ] Step 4 可逆性：指出这条迁移在已有数据上会失败，且回滚路径未说明
- [ ] 决策至少为 `caution`；回滚方案缺失时为 `stop`
- [ ] 明确说明"行数少"不是放行理由

**反例 / Must not**

- 不得因为 diff 小就判 `pass`
- 不得替使用者改写迁移脚本

## Case 3: 用户要求逐行审

**输入 / Input**

用户：你别按风险挑了，从第一行到最后一行给我逐行审一遍。

**期望 / Expected**

- [ ] 说明本 skill 的设计就是按风险分流，不做逐行精读，并说明原因（逐行读会把注意力摊平）
- [ ] 仍然交付四步走查结果与决策
- [ ] 按正文阈值表指出哪几段必须人工逐段过，判据与 `diff_risk.py` 打印的一致：越过文件数或行数阈值时是全部 hunk；
      动到迁移、鉴权、密钥、CI、配置、依赖文件，锁文件新增了包，或出现危险 hunk 时，是那几段
- [ ] 说明人工逐段过完成之前决策不会是 `pass`

**反例 / Must not**

- 不得为了迎合而假装做了逐行审
- 不得因为边界不符就不产出走查结果

## Case 4: 拿不到 diff，只有一段口头描述

**输入 / Input**

用户：AI 说它"优化了缓存逻辑并顺手修了几个小问题"，我没保存 diff。能审吗？

**期望 / Expected**

- [ ] 明确说明没有 diff 就做不了 Step 2 与 Step 3，不猜改了什么
- [ ] 指出"顺手修了几个小问题"这句话本身就是范围蔓延的信号
- [ ] 给出最小的补材料清单（`git diff` 或 `git show <commit>` 的输出、改动文件列表、有没有动测试、配置与迁移）
- [ ] 在拿到材料之前不给决策：没有 Verdict 一栏，`caution` 也不给
- [ ] Diff stats 写"not computed"，不编数字，也不假装跑过 `diff_risk.py`

**反例 / Must not**

- 不得根据描述臆测 diff 内容并给出 `pass` / `caution` / `stop`
- 不得把"听起来是小改动"当作证据

## Case 5: 没有 unified diff，只有改前改后两段代码

**输入 / Input**

请求是"给 `get_user` 加缓存"。用户贴了两段代码，没有 diff：

改之前：

```python
def get_user(user_id):
    row = db.fetch_one("SELECT * FROM users WHERE id = %s", (user_id,))
    return User(**row)
```

AI 改之后：

```python
def get_user(user_id):
    cached = cache.get(f"user:{user_id}")
    if cached:
        return cached
    row = db.fetch_one("SELECT * FROM users WHERE id = %s", (user_id,))
    user = User(**row)
    cache.set(f"user:{user_id}", user, ttl=3600)
    return user
```

**期望 / Expected**

- [ ] 照常走完四步并给出决策（这不是"只有口头描述"的情况）
- [ ] Diff stats 写"not computed (no unified diff)"，或者按两段代码手数并标 "counted by hand"
- [ ] 置信度最多 medium，并写明没看到什么：别的文件、用户资料更新时的缓存失效、测试
- [ ] 指出一小时 TTL 会让改过的用户资料最多旧一小时，这是意图之外的副作用，需要确认

**反例 / Must not**

- 不得因为没有 unified diff 就拒绝给决策
- 不得声称"diff_risk.py 统计显示……"
- 不得给出 high 置信度

## Case 6: 粘贴在聊天里的 diff，里面有危险 hunk

**输入 / Input**

`tests/fixtures/ai-diff-review-protocol/pasted-cache-change.txt` 原样粘贴：一段说明文字、一个 ```diff 代码块
（没有 `diff --git` 行，空白上下文行的行首空格已丢失）、最后一句"帮我看看这个能不能合"。
AI 自称"给导出功能加了缓存，顺手清理了测试"。

**期望 / Expected**

- [ ] 把粘贴的原文存成文件交给 `diff_risk.py`，不要求使用者先去装 Git 或重新导出
- [ ] Diff stats 写出 3 个文件、+8/−4，并报出五个 hunk 信号：`app/export.py` 第 9 行 `pickle.load`（unsafe-deserialization）、
      第 12 行 `subprocess.run(f"rm -rf {CACHE_DIR}/*", shell=True)`（shell-exec 与 recursive-delete）、
      迁移第 1 行 `ADD COLUMN cache_key text NOT NULL`（not-null-without-default）、
      `tests/test_export.py` 旧第 6 行被删的断言（deleted-assertion）；写明必须人工逐段过这三段
- [ ] 决策为 `stop`：迁移和反序列化这两处高风险边界改了，却没有可信的验证，唯一相关的测试断言还被删了
- [ ] 指出 `pickle.load` 读的是 `/tmp` 下别人也能写的文件，`test_load_cached` 删掉断言后只剩"不报错"；
      要审这份测试时交给 `ai-generated-test-auditor`
- [ ] 指出"顺手清理了测试"与"加缓存"的请求不符

**反例 / Must not**

- 不得因为 diff 只有 12 行就判 `pass`
- 不得在报告里只写"脚本报了 5 个信号"而不说每个信号在哪一行、为什么危险
- 不得替使用者改写这份代码
