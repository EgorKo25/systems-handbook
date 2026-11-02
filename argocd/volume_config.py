"""Provisional XXV; registration/publication belongs to the coordinator."""
CONFIG=dict(volume='XXV',short='Argo CD',
 title='Argo CD: GitOps, согласование состояния и эксплуатация',
 description='Поставка, установка, репозитории, рендеринг, сравнение, политики синхронизации, права и восстановление Argo CD.',
 revision='2 ноября 2026',
 sections=[
  ('Начало',['00-route','argocd-01-gitops']),
  ('Книга I · Собственный управляющий контур',['argocd-02-distribution','argocd-03-install','argocd-04-architecture','argocd-05-application']),
  ('Книга II · От исходников к объектам',['argocd-06-render','argocd-07-diff-health','argocd-08-sync','argocd-09-waves-hooks','argocd-10-ownership']),
  ('Книга III · Много приложений и границы доверия',['argocd-11-applicationset','argocd-12-repositories','argocd-13-access']),
  ('Книга IV · Сохранение услуги',['argocd-14-recovery','argocd-15-capacity','argocd-16-offline','argocd-18-diagnostics']),
  ('Продолжаемый практикум',['argocd-17-lab','argocd-19-sources']),
  ('Справочник',['99-glossary'])],
 base_terms=[],term_modules=['reference'],command_modules=['reference'],diagram_modules=['diagrams'],
 blurb='Git и желаемое состояние → установка → получение и рендеринг → сравнение и синхронизация → права → резерв, измерение и восстановление.')
