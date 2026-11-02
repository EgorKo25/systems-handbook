{{- define "ledger.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- define "ledger.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name | quote }}
app.kubernetes.io/instance: {{ .Release.Name | quote }}
{{- end -}}
{{- define "ledger.labels" -}}
{{ include "ledger.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service | quote }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | quote }}
{{- end -}}
{{- define "ledger.configData" -}}
MESSAGE: {{ .Values.config.message | quote }}
{{- end -}}
{{- define "ledger.secretName" -}}
{{- if .Values.credentials.create -}}
{{- printf "%s-auth" (include "ledger.fullname" .) -}}
{{- else -}}
{{- .Values.credentials.existingSecret -}}
{{- end -}}
{{- end -}}
