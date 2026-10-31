import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type DragEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { PageTitle } from "../components/PageTitle";
import { navGroups, type NavGroup } from "../components/Navigation";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import {
  applyMenuOrder,
  MENU_ORDER_KEY,
  menuOrderOf,
  moved,
  type MenuOrder,
} from "../lib/menuOrder";
import { settingOf, usePlatformSettings } from "../lib/phase9";
import { p9Keys } from "../lib/phase9Api";

/** One list that reorders by dragging, or with the up and down buttons (keyboard and screen readers). */
function Sortable<T>({
  items,
  keyOf,
  labelOf,
  onChange,
  name,
}: {
  items: readonly T[];
  keyOf: (x: T) => string;
  labelOf: (x: T) => string;
  onChange: (next: T[]) => void;
  name: string;
}) {
  const { t } = useTranslation();
  const [dragging, setDragging] = useState<number | null>(null);
  const drop = (e: DragEvent, to: number) => {
    e.preventDefault();
    if (dragging !== null && dragging !== to)
      onChange(moved(items, dragging, to));
    setDragging(null);
  };
  return (
    <ol className="sortable" aria-label={name}>
      {items.map((x, i) => (
        <li
          key={keyOf(x)}
          className={`sortable__item ${dragging === i ? "sortable__item--dragging" : ""}`}
          draggable
          onDragStart={() => setDragging(i)}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => drop(e, i)}
          onDragEnd={() => setDragging(null)}
          data-testid={`sortable-${keyOf(x)}`}
        >
          <span className="sortable__handle" aria-hidden="true">
            ⠿
          </span>
          <span className="sortable__label">{labelOf(x)}</span>
          <button
            type="button"
            className="btn btn--small"
            disabled={i === 0}
            aria-label={t("menuOrder.up", { name: labelOf(x) })}
            onClick={() => onChange(moved(items, i, i - 1))}
          >
            ↑
          </button>
          <button
            type="button"
            className="btn btn--small"
            disabled={i === items.length - 1}
            aria-label={t("menuOrder.down", { name: labelOf(x) })}
            onClick={() => onChange(moved(items, i, i + 1))}
          >
            ↓
          </button>
        </li>
      ))}
    </ol>
  );
}

function orderOf(groups: readonly NavGroup[]): MenuOrder {
  return {
    groups: groups.map((g) => g.key),
    items: Object.fromEntries(
      groups.map((g) => [g.key, g.items.map((i) => i.to)]),
    ),
  };
}

/** Review point 9 (phase D): the system administrator orders the menu by drag and drop; saved for every user. */
export function MenuOrderPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const qc = useQueryClient();
  const reasonId = useId();
  const settings = usePlatformSettings();
  const setting = settingOf(settings.data, MENU_ORDER_KEY);
  const [draft, setDraft] = useState<NavGroup[] | null>(null);
  const [reason, setReason] = useState("");
  const save = useMutation({
    mutationFn: (groups: NavGroup[]) =>
      api.savePlatformSetting(MENU_ORDER_KEY, {
        value: orderOf(groups),
        version: setting?.version ?? 0,
        reason: reason.trim(),
      }),
    onSuccess: () => {
      setDraft(null);
      setReason("");
      void qc.invalidateQueries({ queryKey: p9Keys.settings });
    },
  });
  if (!user) return null;
  if (settings.isPending) return <Loading />;
  if (settings.isError)
    return (
      <ErrorBox
        error={settings.error}
        onRetry={() => void settings.refetch()}
      />
    );
  // The administrator sees every link of the platform: the order then holds for each role's subset.
  const saved = applyMenuOrder(
    navGroups(user.identity, t),
    menuOrderOf(setting?.value),
  );
  const groups = draft ?? saved;
  const editable = setting?.editable ?? false;
  const setGroup = (key: string, items: NavGroup["items"]) =>
    setDraft(groups.map((g) => (g.key === key ? { ...g, items } : g)));
  return (
    <div className="page menu-order-page">
      <p>
        <Link to="/settings">{t("menuOrder.back")}</Link>
      </p>
      <div className="page__head">
        <PageTitle icon="menu" tone="slate">
          {t("menuOrder.title")}
        </PageTitle>
      </div>
      <p className="muted">{t("menuOrder.intro")}</p>
      {!editable && (
        <p className="alert alert--info">{t("menuOrder.readOnly")}</p>
      )}
      <fieldset disabled={!editable || save.isPending} className="menu-order">
        <legend>{t("menuOrder.groups")}</legend>
        <Sortable
          items={groups}
          keyOf={(g) => g.key}
          labelOf={(g) => g.label}
          onChange={setDraft}
          name={t("menuOrder.groups")}
        />
        {groups.map((g) => (
          <details key={g.key} className="menu-order__group">
            <summary>
              <Icon name={g.icon} size={18} /> {g.label}
            </summary>
            <Sortable
              items={g.items}
              keyOf={(i) => i.to}
              labelOf={(i) => i.label}
              onChange={(items) => setGroup(g.key, items)}
              name={g.label}
            />
          </details>
        ))}
        <div className="field">
          <label htmlFor={reasonId}>
            {t("menuOrder.reason")} <span className="required">*</span>
          </label>
          <input
            id={reasonId}
            value={reason}
            maxLength={300}
            dir="auto"
            onChange={(e) => setReason(e.target.value)}
          />
        </div>
        <div className="form-row">
          <button
            type="button"
            className="btn btn--primary"
            disabled={draft === null || reason.trim().length < 3}
            onClick={() => draft && save.mutate(draft)}
          >
            {t("menuOrder.save")}
          </button>
          <button
            type="button"
            className="btn"
            disabled={draft === null}
            onClick={() => setDraft(null)}
          >
            {t("menuOrder.undo")}
          </button>
          <button
            type="button"
            className="btn"
            onClick={() => setDraft(navGroups(user.identity, t))}
            title={t("menuOrder.builtInHint")}
          >
            {t("menuOrder.builtIn")}
          </button>
        </div>
        {save.isError && (
          <p role="alert" className="field__error">
            {t(errorMessageKey(save.error))}
          </p>
        )}
        {save.isSuccess && <p role="status">{t("menuOrder.saved")}</p>}
      </fieldset>
    </div>
  );
}
