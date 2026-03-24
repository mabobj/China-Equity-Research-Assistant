import { DbConsole } from "@/components/db-console";
import { PageShell } from "@/components/page-shell";

export default function ReviewsPage() {
  return (
    <PageShell
      title="数据排查台"
      description="面向数据操作人员，提供数据库表清单和只读 SQL 查询能力，用于快速定位补全异常与数据缺口。"
    >
      <DbConsole />
    </PageShell>
  );
}
