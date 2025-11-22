import tkinter as tk
from tkinter import ttk, messagebox
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional
import json
import os

EXPENSE_CATEGORIES = [
    "Транспорт",
    "Аренда",
    "Коммунальные услуги",
    "Связь и интернет",
    "Прочие операционные расходы",
]

INCOME_CATEGORIES = [
    "Оказание услуг",
    "Продажа товаров",
    "Проценты и прочие доходы",
    "Прочие доходы",
]

BASE_CURRENCY = "RUB"


@dataclass
class Account:
    id: int
    name: str
    acc_type: str
    currency: str = BASE_CURRENCY
    initial_balance: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "acc_type": self.acc_type,
            "currency": self.currency,
            "initial_balance": self.initial_balance,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Account":
        return cls(
            id=data["id"],
            name=data["name"],
            acc_type=data.get("acc_type", "Счет"),
            currency=data.get("currency", BASE_CURRENCY),
            initial_balance=float(data.get("initial_balance", 0.0)),
        )

@dataclass
class Transaction:
    id: int
    date: datetime
    account_id: int
    category: str
    description: str
    amount: float
    currency: str = BASE_CURRENCY

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "date": self.date.isoformat(),
            "account_id": self.account_id,
            "category": self.category,
            "description": self.description,
            "amount": self.amount,
            "currency": self.currency,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Transaction":
        return cls(
            id=data["id"],
            date=datetime.fromisoformat(data["date"]),
            account_id=int(data.get("account_id", 1)),
            category=data.get("category", "Прочие операционные расходы"),
            description=data.get("description", ""),
            amount=float(data.get("amount", 0.0)),
            currency=data.get("currency", BASE_CURRENCY),
        )



class DataStore:
    def __init__(self, path: str = "fintech_data_full.json"):
        self.path = path
        self.accounts: List[Account] = []
        self.transactions: List[Transaction] = []
        self.settings: Dict[str, str] = {
            "user_name": "Компания",
        }
        self._next_acc_id = 1
        self._next_tx_id = 1

        self.load()
        if not self.accounts:
            self.add_account("Расчетный счет", "Карта", BASE_CURRENCY, 0.0)
            self.save()


    def get_user_name(self) -> str:
        return self.settings.get("user_name", "Компания")


    def add_account(
        self,
        name: str,
        acc_type: str,
        currency: str,
        initial_balance: float,
    ) -> Account:
        acc = Account(
            id=self._next_acc_id,
            name=name,
            acc_type=acc_type,
            currency=currency,
            initial_balance=initial_balance,
        )
        self.accounts.append(acc)
        self._next_acc_id += 1
        self.save()
        return acc

    def update_account(
        self,
        acc_id: int,
        name: str,
        acc_type: str,
        initial_balance: float,
    ) -> None:
        acc = self.get_account_by_id(acc_id)
        if not acc:
            return
        acc.name = name
        acc.acc_type = acc_type
        acc.initial_balance = initial_balance
        self.save()

    def get_accounts(self) -> List[Account]:
        return list(self.accounts)

    def get_account_by_id(self, acc_id: int) -> Optional[Account]:
        for acc in self.accounts:
            if acc.id == acc_id:
                return acc
        return None

    def get_account_balance(self, acc_id: int) -> float:
        acc = self.get_account_by_id(acc_id)
        if not acc:
            return 0.0
        total = acc.initial_balance
        for t in self.transactions:
            if t.account_id == acc_id and t.currency == acc.currency:
                total += t.amount
        return total

    def get_overall_balance(self) -> float:
        total = 0.0
        for acc in self.accounts:
            total += self.get_account_balance(acc.id)
        return total


    def add_transaction(
        self,
        account_id: int,
        amount: float,
        category: str,
        description: str,
        date: Optional[datetime] = None,
    ) -> Transaction:
        if date is None:
            date = datetime.now()
        tx = Transaction(
            id=self._next_tx_id,
            date=date,
            account_id=account_id,
            category=category,
            description=description,
            amount=amount,
            currency=BASE_CURRENCY,
        )
        self.transactions.append(tx)
        self._next_tx_id += 1
        self.save()
        return tx

    def update_transaction(
        self,
        tx_id: int,
        account_id: int,
        amount: float,
        category: str,
        description: str,
    ) -> None:
        tx = self.get_transaction_by_id(tx_id)
        if not tx:
            return
        tx.account_id = account_id
        tx.amount = amount
        tx.category = category
        tx.description = description
        self.save()

    def delete_transaction(self, tx_id: int) -> None:
        self.transactions = [t for t in self.transactions if t.id != tx_id]
        self.save()

    def get_transactions(self) -> List[Transaction]:
        return sorted(self.transactions, key=lambda t: t.date, reverse=True)

    def get_transaction_by_id(self, tx_id: int) -> Optional[Transaction]:
        for t in self.transactions:
            if t.id == tx_id:
                return t
        return None

    def get_month_summary(self):
        """Возвращает доход (>0), расход (<0) и суммы по категориям за текущий месяц."""
        now = datetime.now()
        income = 0.0
        expense = 0.0
        by_category: Dict[str, float] = {}

        for t in self.transactions:
            if t.date.year == now.year and t.date.month == now.month:
                if t.amount >= 0:
                    income += t.amount
                else:
                    expense += t.amount
                by_category[t.category] = by_category.get(t.category, 0.0) + t.amount

        return income, expense, by_category

    # ---- экспорт ----

    def export_csv(self, filename: str = "Отчет.csv") -> None:
        """
        Экспорт в CSV с разделителем ; и заголовками на русском.
        Кодировка utf-8-sig, чтобы Excel корректно отображал текст.
        """
        lines = ["ID;Дата;Счет;Категория;Описание;Сумма;Валюта"]
        acc_by_id = {a.id: a for a in self.accounts}
        for t in self.get_transactions():
            acc_name = acc_by_id.get(t.account_id).name if acc_by_id.get(t.account_id) else "?"
            desc = t.description.replace(";", ",")
            line = (
                f"{t.id};{t.date.strftime('%Y-%m-%d %H:%M')};"
                f"{acc_name};{t.category};\"{desc}\";{t.amount};{BASE_CURRENCY}"
            )
            lines.append(line)

        with open(filename, "w", encoding="utf-8-sig") as f:
            f.write("\n".join(lines))

    # ---- load / save ----

    def load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.accounts = [
                Account.from_dict(item) for item in raw.get("accounts", [])
            ]
            self.transactions = [
                Transaction.from_dict(item) for item in raw.get("transactions", [])
            ]
            if self.accounts:
                self._next_acc_id = max(a.id for a in self.accounts) + 1
            if self.transactions:
                self._next_tx_id = max(t.id for t in self.transactions) + 1
            self.settings.update(raw.get("settings", {}))
        except Exception as e:
            print("Ошибка загрузки данных:", e)

    def save(self) -> None:
        try:
            data = {
                "accounts": [a.to_dict() for a in self.accounts],
                "transactions": [t.to_dict() for t in self.transactions],
                "settings": self.settings,
            }
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("Ошибка сохранения данных:", e)


class Card(ttk.Frame):
    def __init__(self, parent, title: str, value_var: tk.StringVar, accent: bool = False):
        super().__init__(parent, style="Card.TFrame", padding=12)
        self.columnconfigure(0, weight=1)
        title_style = "CardTitleAccent.TLabel" if accent else "CardTitle.TLabel"
        value_style = "CardValueAccent.TLabel" if accent else "CardValue.TLabel"

        ttk.Label(self, text=title, style=title_style).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(self, textvariable=value_var, style=value_style).grid(
            row=1, column=0, sticky="w", pady=(6, 0)
        )

class AddAccountDialog(tk.Toplevel):
    def __init__(self, parent, store: DataStore, on_save, account_id: Optional[int] = None):
        super().__init__(parent)
        self.store = store
        self.on_save = on_save
        self.account_id = account_id

        self.title("Редактирование счета" if account_id else "Новый счет")
        self.resizable(False, False)
        self.configure(bg="#FFFFFF")
        self.transient(parent)
        self.grab_set()

        self._build()
        self._center()

    def _build(self):
        frm = ttk.Frame(self, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text="Название:").grid(row=0, column=0, sticky="e", pady=4)
        self.name_var = tk.StringVar(value="Новый счет")

        ttk.Entry(frm, textvariable=self.name_var).grid(
            row=0, column=1, sticky="ew", pady=4
        )

        ttk.Label(frm, text="Тип:").grid(row=1, column=0, sticky="e", pady=4)
        self.type_var = tk.StringVar(value="Карта")
        ttk.Combobox(
            frm,
            textvariable=self.type_var,
            values=["Карта", "Наличные", "Депозит"],
            state="readonly",
        ).grid(row=1, column=1, sticky="w", pady=4)

        ttk.Label(frm, text="Валюта:").grid(row=2, column=0, sticky="e", pady=4)
        ttk.Label(frm, text=BASE_CURRENCY).grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(frm, text="Начальный баланс:").grid(
            row=3, column=0, sticky="e", pady=4
        )
        self.balance_entry = ttk.Entry(frm)
        self.balance_entry.insert(0, "0")
        self.balance_entry.grid(row=3, column=1, sticky="ew", pady=4)

        if self.account_id is not None:
            acc = self.store.get_account_by_id(self.account_id)
            if acc:
                self.name_var.set(acc.name)
                self.type_var.set(acc.acc_type)
                self.balance_entry.delete(0, "end")
                self.balance_entry.insert(0, str(acc.initial_balance))

        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(btns, text="Отмена", command=self.destroy).grid(
            row=0, column=0, padx=(0, 6)
        )
        ttk.Button(
            btns,
            text="Сохранить",
            style="Accent.TButton",
            command=self._save,
        ).grid(row=0, column=1)

    def _center(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"+{x}+{y}")

    def _save(self):
        name = self.name_var.get().strip() or "Счет"
        acc_type = self.type_var.get() or "Счет"
        try:
            bal = float(self.balance_entry.get().replace(",", ".").replace(" ", ""))
        except ValueError:
            messagebox.showerror("Ошибка", "Неверный баланс.")
            return

        if self.account_id is None:
            self.store.add_account(name, acc_type, BASE_CURRENCY, bal)
        else:
            self.store.update_account(self.account_id, name, acc_type, bal)

        self.on_save()
        self.destroy()


class AddTransactionDialog(tk.Toplevel):
    def __init__(self, parent, store: DataStore, on_save, tx_id: Optional[int] = None):
        super().__init__(parent)
        self.store = store
        self.on_save = on_save
        self.tx_id = tx_id

        self.title("Редактирование операции" if tx_id else "Новая операция")
        self.resizable(False, False)
        self.configure(bg="#FFFFFF")
        self.transient(parent)
        self.grab_set()

        self._build()
        self._center()

    def _build(self):
        frm = ttk.Frame(self, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text="Счет:").grid(row=0, column=0, sticky="e", pady=4)
        self.acc_var = tk.StringVar()
        accounts = self.store.get_accounts()
        if not accounts:
            messagebox.showerror("Ошибка", "Нет счетов, сначала создайте счет.")
            self.destroy()
            return
        acc_names = [a.name for a in accounts]
        self.acc_map = {a.name: a.id for a in accounts}
        self.acc_combo = ttk.Combobox(
            frm, textvariable=self.acc_var, values=acc_names, state="readonly"
        )
        self.acc_combo.grid(row=0, column=1, sticky="ew", pady=4)
        self.acc_combo.current(0)

        ttk.Label(frm, text="Тип:").grid(row=1, column=0, sticky="e", pady=4)
        self.type_var = tk.StringVar(value="Расход")
        self.type_combo = ttk.Combobox(
            frm,
            textvariable=self.type_var,
            values=["Расход", "Доход"],
            state="readonly",
            width=10,
        )
        self.type_combo.grid(row=1, column=1, sticky="w", pady=4)
        self.type_combo.bind("<<ComboboxSelected>>", lambda e: self._update_categories())

        ttk.Label(frm, text="Сумма:").grid(row=2, column=0, sticky="e", pady=4)
        self.amount_entry = ttk.Entry(frm)
        self.amount_entry.grid(row=2, column=1, sticky="ew", pady=4)

        ttk.Label(frm, text="Категория:").grid(row=3, column=0, sticky="e", pady=4)
        self.cat_var = tk.StringVar()
        self.cat_combo = ttk.Combobox(
            frm,
            textvariable=self.cat_var,
            state="readonly",
        )
        self.cat_combo.grid(row=3, column=1, sticky="w", pady=4)

        ttk.Label(frm, text="Описание:").grid(row=4, column=0, sticky="e", pady=4)
        self.desc_entry = ttk.Entry(frm)
        self.desc_entry.grid(row=4, column=1, sticky="ew", pady=4)

        self.type_var.set("Расход")
        self._update_categories()

        if self.tx_id is not None:
            tx = self.store.get_transaction_by_id(self.tx_id)
            if tx:
                acc = self.store.get_account_by_id(tx.account_id)
                if acc:
                    self.acc_var.set(acc.name)
                self.type_var.set("Доход" if tx.amount >= 0 else "Расход")
                self._update_categories()
                if tx.category in self.cat_combo["values"]:
                    self.cat_var.set(tx.category)
                self.amount_entry.insert(0, str(abs(tx.amount)))
                self.desc_entry.insert(0, tx.description)

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(btns, text="Отмена", command=self.destroy).grid(
            row=0, column=0, padx=(0, 6)
        )
        ttk.Button(
            btns,
            text="Сохранить",
            style="Accent.TButton",
            command=self._save,
        ).grid(row=0, column=1)

    def _update_categories(self):
        if self.type_var.get() == "Доход":
            cats = INCOME_CATEGORIES
        else:
            cats = EXPENSE_CATEGORIES
        self.cat_combo["values"] = cats
        if self.cat_var.get() not in cats:
            self.cat_var.set(cats[0])

    def _center(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"+{x}+{y}")

    def _save(self):
        acc_name = self.acc_var.get()
        acc_id = self.acc_map.get(acc_name)
        if not acc_id:
            messagebox.showerror("Ошибка", "Не выбран счет.")
            return

        try:
            amount = float(self.amount_entry.get().replace(",", ".").replace(" ", ""))
        except ValueError:
            messagebox.showerror("Ошибка", "Неверная сумма.")
            return

        tx_type = self.type_var.get()
        if tx_type == "Расход" and amount > 0:
            amount = -amount

        category = self.cat_var.get()
        if not category:
            category = (INCOME_CATEGORIES if tx_type == "Доход" else EXPENSE_CATEGORIES)[0]

        desc = self.desc_entry.get().strip() or "-"

        if self.tx_id is None:
            self.store.add_transaction(
                account_id=acc_id,
                amount=amount,
                category=category,
                description=desc,
            )
        else:
            self.store.update_transaction(
                tx_id=self.tx_id,
                account_id=acc_id,
                amount=amount,
                category=category,
                description=desc,
            )

        self.on_save()
        self.destroy()

class OverviewPage(ttk.Frame):
    def __init__(self, parent, store: DataStore):
        super().__init__(parent)
        self.store = store
        self._build()

    def _build(self):
        self.columnconfigure(0, weight=1)

        ttk.Label(self, text="📌 Общий обзор", style="Header.TLabel").grid(
            row=0, column=0, sticky="w", padx=16, pady=(16, 0)
        )

        self.info_var = tk.StringVar()
        ttk.Label(self, textvariable=self.info_var, style="Subheader.TLabel").grid(
            row=1, column=0, sticky="w", padx=16, pady=(4, 12)
        )

        cards = ttk.Frame(self)
        cards.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))
        cards.columnconfigure((0, 1, 2), weight=1)

        self.balance_var = tk.StringVar()
        self.income_var = tk.StringVar()
        self.expense_var = tk.StringVar()

        Card(cards, "Совокупный баланс", self.balance_var, accent=True).grid(
            row=0, column=0, sticky="nsew", padx=(0, 4)
        )
        Card(cards, "Доход за текущий месяц", self.income_var).grid(
            row=0, column=1, sticky="nsew", padx=4
        )
        Card(cards, "Расход за текущий месяц", self.expense_var).grid(
            row=0, column=2, sticky="nsew", padx=(4, 0)
        )

        self.refresh()

    def refresh(self):
        income, expense, _ = self.store.get_month_summary()
        balance = self.store.get_overall_balance()
        self.info_var.set(f"{self.store.get_user_name()} • валюта учета: {BASE_CURRENCY}")
        self.balance_var.set(f"{balance:,.2f} {BASE_CURRENCY}")
        self.income_var.set(f"{income:,.2f} {BASE_CURRENCY}")
        self.expense_var.set(f"{expense:,.2f} {BASE_CURRENCY}")


class AccountsPage(ttk.Frame):
    def __init__(self, parent, store: DataStore, on_changed):
        super().__init__(parent)
        self.store = store
        self.on_changed = on_changed
        self._build()

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="Счета", style="Header.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(
            header,
            text="Добавить счет",
            style="Accent.TButton",
            command=lambda: AddAccountDialog(self, self.store, self._after_change),
        ).grid(row=0, column=1, sticky="e")

        frame = ttk.Frame(self)
        frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        cols = ("name", "type", "currency", "initial", "current")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", style="Data.Treeview")
        self.tree.grid(row=0, column=0, sticky="nsew")

        headers = {
            "name": "Название",
            "type": "Тип",
            "currency": "Валюта",
            "initial": "Начальный баланс",
            "current": "Текущий баланс",
        }
        for col, text in headers.items():
            self.tree.heading(col, text=text)

        self.tree.column("name", width=180, anchor="w")
        self.tree.column("type", width=120, anchor="w")
        self.tree.column("currency", width=70, anchor="center")
        self.tree.column("initial", width=130, anchor="e")
        self.tree.column("current", width=130, anchor="e")

        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)

        self.tree.bind("<Double-1>", self._on_double_click)

        self.refresh()

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        for acc in self.store.get_accounts():
            bal = self.store.get_account_balance(acc.id)
            self.tree.insert(
                "",
                "end",
                iid=str(acc.id),
                values=(
                    acc.name,
                    acc.acc_type,
                    acc.currency,
                    f"{acc.initial_balance:,.2f}",
                    f"{bal:,.2f}",
                ),
            )

    def _on_double_click(self, event):
        item = self.tree.focus()
        if not item:
            return
        acc_id = int(item)
        AddAccountDialog(self, self.store, self._after_change, account_id=acc_id)

    def _after_change(self):
        self.refresh()
        self.on_changed()


class TransactionsPage(ttk.Frame):
    def __init__(self, parent, store: DataStore, on_changed):
        super().__init__(parent)
        self.store = store
        self.on_changed = on_changed
        self._build()

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="Операции", style="Header.TLabel").grid(
            row=0, column=0, sticky="w"
        )

        ttk.Button(
            header,
            text="Новая операция",
            style="Accent.TButton",
            command=lambda: AddTransactionDialog(self, self.store, self._after_change),
        ).grid(row=0, column=1, sticky="e")

        filter_frame = ttk.Frame(self)
        filter_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 4))
        filter_frame.columnconfigure(2, weight=1)

        ttk.Label(filter_frame, text="Счет:", style="Subheader.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.filter_acc_var = tk.StringVar(value="Все")
        acc_names = ["Все"] + [a.name for a in self.store.get_accounts()]
        self.filter_acc_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.filter_acc_var,
            values=acc_names,
            state="readonly",
            width=25,
        )
        self.filter_acc_combo.grid(row=0, column=1, sticky="w", padx=(4, 0))
        self.filter_acc_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        btn_edit = ttk.Button(
            filter_frame,
            text="Редактировать",
            command=self._edit_selected,
        )
        btn_edit.grid(row=0, column=3, sticky="e", padx=(0, 4))

        btn_delete = ttk.Button(
            filter_frame,
            text="Удалить",
            command=self._delete_selected,
        )
        btn_delete.grid(row=0, column=4, sticky="e", padx=(0, 4))

        btn_export = ttk.Button(
            filter_frame,
            text="Экспорт CSV",
            command=self._export,
        )
        btn_export.grid(row=0, column=5, sticky="e")

        frame = ttk.Frame(self)
        frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        cols = ("date", "account", "category", "description", "amount")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", style="Data.Treeview")
        self.tree.grid(row=0, column=0, sticky="nsew")

        # Цвета строк по типу операции и зебра
        self.tree.tag_configure("income", foreground="#16A34A")   # зеленый
        self.tree.tag_configure("expense", foreground="#DC2626")  # красный
        self.tree.tag_configure("row_odd", background="#F9FAFB")
        self.tree.tag_configure("row_even", background="#FFFFFF")

        headers = {
            "date": "Дата",
            "account": "Счет",
            "category": "Категория",
            "description": "Описание",
            "amount": "Сумма (RUB)",
        }
        for col, text in headers.items():
            self.tree.heading(col, text=text)

        self.tree.column("date", width=140, anchor="w")
        self.tree.column("account", width=150, anchor="w")
        self.tree.column("category", width=160, anchor="w")
        self.tree.column("description", width=260, anchor="w")
        self.tree.column("amount", width=120, anchor="e")

        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)

        self.tree.bind("<Double-1>", self._on_double_click)

        self.refresh()

    def _get_selected_tx_id(self) -> Optional[int]:
        selection = self.tree.selection()
        if not selection:
            return None
        try:
            return int(selection[0])
        except ValueError:
            return None

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        acc_filter = self.filter_acc_var.get()
        acc_by_id = {a.id: a for a in self.store.get_accounts()}

        row_index = 0
        for t in self.store.get_transactions():
            acc = acc_by_id.get(t.account_id)
            acc_name = acc.name if acc else "?"
            if acc_filter != "Все" and acc_name != acc_filter:
                continue

            base_tags = []
            base_tags.append("income" if t.amount >= 0 else "expense")
            base_tags.append("row_even" if row_index % 2 == 0 else "row_odd")
            row_index += 1

            self.tree.insert(
                "",
                "end",
                iid=str(t.id),
                values=(
                    t.date.strftime("%Y-%m-%d %H:%M"),
                    acc_name,
                    t.category,
                    t.description,
                    f"{t.amount:,.2f}",
                ),
                tags=tuple(base_tags),
            )

    def _on_double_click(self, event):
        tx_id = self._get_selected_tx_id()
        if tx_id is None:
            return
        AddTransactionDialog(self, self.store, self._after_change, tx_id=tx_id)

    def _edit_selected(self):
        tx_id = self._get_selected_tx_id()
        if tx_id is None:
            messagebox.showinfo("Редактирование", "Выберите операцию для редактирования.")
            return
        AddTransactionDialog(self, self.store, self._after_change, tx_id=tx_id)

    def _delete_selected(self):
        tx_id = self._get_selected_tx_id()
        if tx_id is None:
            messagebox.showinfo("Удаление", "Выберите операцию для удаления.")
            return
        if not messagebox.askyesno("Подтверждение", "Удалить выбранную операцию?"):
            return
        self.store.delete_transaction(tx_id)
        self._after_change()

    def _after_change(self):
        self.refresh()
        self.on_changed()

    def _export(self):
        try:
            self.store.export_csv()
            messagebox.showinfo(
                "Отчет успешно сохранен",
                "Отчет успешно сохранен в файл Отчет.csv.",
            )
        except Exception as e:
            messagebox.showerror("Ошибка экспорта", str(e))


class AnalyticsPage(ttk.Frame):
    def __init__(self, parent, store: DataStore):
        super().__init__(parent)
        self.store = store
        self._build()

    def _build(self):
        self.columnconfigure(0, weight=2)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        ttk.Label(self, text="Аналитика", style="Header.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 4)
        )

        self.subtitle_var = tk.StringVar()
        ttk.Label(self, textvariable=self.subtitle_var, style="Subheader.TLabel").grid(
            row=0, column=1, sticky="e", padx=10, pady=(10, 4)
        )

        self.canvas = tk.Canvas(
            self,
            height=260,
            bd=0,
            highlightthickness=0,
            bg="#FFFFFF",
        )
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=(10, 4), pady=(0, 10))
        # важно: перерисовывать при изменении размеров
        self.canvas.bind("<Configure>", lambda e: self._draw_chart())

        right = ttk.Frame(self)
        right.grid(row=1, column=1, sticky="nsew", padx=(4, 10), pady=(0, 10))
        right.columnconfigure(0, weight=1)
        ttk.Label(right, text="Краткие выводы", style="Subheader.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        self.text = tk.Text(
            right,
            height=10,
            wrap="word",
            bd=1,
            relief="solid",
            highlightthickness=0,
            bg="#FFFFFF",
            fg="#111827",
            insertbackground="#111827",
            font=("Segoe UI", 9),
        )
        self.text.grid(row=1, column=0, sticky="nsew")
        self.text.configure(state="disabled")

        self.refresh()

    def refresh(self):
        income, expense, by_cat = self.store.get_month_summary()
        self.subtitle_var.set("Текущий месяц, валюта: RUB")
        self._update_text(income, expense, by_cat)
        self._draw_chart()

    def _update_text(self, income: float, expense: float, by_cat: Dict[str, float]):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")

        net = income + expense

        if income == 0 and expense == 0:
            self.text.insert(
                "end",
                "За текущий месяц движения по счетам отсутствуют.",
            )
            self.text.configure(state="disabled")
            return

        main_cat = None
        if by_cat:
            main_cat = max(by_cat.items(), key=lambda x: abs(x[1]))

        lines = []
        lines.append(f"1. Доход за месяц: {income:,.2f} RUB.")
        lines.append(f"2. Расход за месяц: {expense:,.2f} RUB.")
        lines.append(f"3. Чистый результат: {net:,.2f} RUB.")
        if main_cat:
            lines.append(
                f"4. Наибольшая по объему категория: {main_cat[0]} ({main_cat[1]:,.2f} RUB)."
            )

        self.text.insert("end", "\n".join(lines))
        self.text.configure(state="disabled")

    def _draw_chart(self):
        self.canvas.delete("all")

        income, expense, _ = self.store.get_month_summary()
        # expense здесь отрицательный, но для высоты берем модуль
        expense_abs = abs(expense)
        net = income + expense

        if income == 0 and expense == 0:
            # нечего рисовать
            return

        w = self.canvas.winfo_width() or 400
        h = self.canvas.winfo_height() or 260
        padding = 40
        bottom = h - padding
        top = padding

        max_val = max(income, expense_abs, abs(net), 1)

        values = [
            ("Доход", income, "#22C55E"),
            ("Расход", expense_abs, "#EF4444"),
            ("Результат", abs(net), "#22C55E" if net >= 0 else "#EF4444"),
        ]
        labels = {
            "Доход": income,
            "Расход": expense,
            "Результат": net,
        }

        bar_width = (w - 2 * padding) / (len(values) * 1.5)
        gap = bar_width / 2

        for i, (name, val_abs, color) in enumerate(values):
            x_center = padding + bar_width / 2 + i * (bar_width + gap)
            x0 = x_center - bar_width / 2
            x1 = x_center + bar_width / 2

            bar_height = (val_abs / max_val) * (h - 2 * padding)
            y0 = bottom - bar_height
            y1 = bottom

            self.canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline="")

            self.canvas.create_text(
                x_center,
                bottom + 15,
                text=name,
                fill="#111827",
                font=("Segoe UI", 9),
            )
            self.canvas.create_text(
                x_center,
                y0 - 10,
                text=f"{labels[name]:,.0f}",
                fill="#111827",
                font=("Segoe UI", 9),
            )


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Финансовая информационная система (RUB)")
        self.geometry("1000x650")
        self.minsize(900, 550)

        self.store = DataStore()
        self._configure_style()
        self._build()

    def _configure_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        # Основные цвета
        bg = "#0F172A"          # темно-синий фон вокруг
        content_bg = "#F3F4F6"  # фон контента
        card_bg = "#FFFFFF"
        text = "#111827"
        text_muted = "#6B7280"
        accent = "#2563EB"
        accent_hover = "#1D4ED8"

        # фон окна
        self.configure(bg=bg)

        # Базовые настройки
        style.configure(
            ".",
            background=content_bg,
            foreground=text,
            font=("Segoe UI", 10)
        )
        style.configure("TFrame", background=content_bg)
        style.configure("TLabel", background=content_bg, foreground=text)

        # Заголовки
        style.configure("Header.TLabel", font=("Segoe UI Semibold", 18))
        style.configure("Subheader.TLabel", font=("Segoe UI", 9), foreground=text_muted)

        # Карточки
        style.configure(
            "Card.TFrame",
            background=card_bg,
            relief="flat",
            borderwidth=0
        )
        style.configure("CardTitle.TLabel", background=card_bg, foreground=text_muted)
        style.configure(
            "CardTitleAccent.TLabel",
            background=card_bg,
            foreground=accent,
        )
        style.configure(
            "CardValue.TLabel",
            background=card_bg,
            foreground=text,
            font=("Segoe UI Semibold", 16),
        )
        style.configure(
            "CardValueAccent.TLabel",
            background=card_bg,
            foreground=accent,
            font=("Segoe UI Semibold", 20),
        )

        # Кнопки
        style.configure(
            "TButton",
            padding=(12, 6),
            background="#E5E7EB",
            foreground=text,
            borderwidth=0,
            focusthickness=0
        )
        style.map(
            "TButton",
            background=[("active", "#D1D5DB"), ("pressed", "#D1D5DB")],
        )
        style.configure(
            "Accent.TButton",
            background=accent,
            foreground="#FFFFFF",
            padding=(14, 6)
        )
        style.map(
            "Accent.TButton",
            background=[("active", accent_hover), ("pressed", accent_hover)],
        )

        # Notebook (вкладки)
        style.configure(
            "TNotebook",
            background=bg,
            borderwidth=0,
            tabmargins=(8, 4, 8, 0),
        )
        style.configure(
            "TNotebook.Tab",
            background="#E5E7EB",
            foreground=text_muted,
            padding=(18, 8),
            font=("Segoe UI", 10),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", card_bg)],
            foreground=[("selected", text)],
        )

        # Таблицы
        style.configure(
            "Data.Treeview",
            background="#FFFFFF",
            fieldbackground="#FFFFFF",
            foreground=text,
            rowheight=24,
            borderwidth=0,
        )
        style.map(
            "Data.Treeview",
            background=[("selected", "#DBEAFE")],
            foreground=[("selected", "#111827")],
        )
        style.configure(
            "Treeview.Heading",
            background="#E5E7EB",
            foreground=text_muted,
            font=("Segoe UI", 9, "bold"),
            relief="flat",
        )

        # Поля ввода / комбобоксы
        style.configure(
            "TEntry",
            foreground=text,
            fieldbackground="#FFFFFF",
            insertcolor=text,
        )
        style.configure(
            "TCombobox",
            foreground=text,
            fieldbackground="#FFFFFF",
            background="#E5E7EB",
        )

    def _build(self):
        # Внешний фрейм на темном фоне
        outer = tk.Frame(self, bg="#0F172A")
        outer.pack(fill="both", expand=True, padx=16, pady=16)
        outer.grid_rowconfigure(1, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        # Верхняя панель (header)
        header = tk.Frame(outer, bg="#0F172A")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title_lbl = tk.Label(
            header,
            text="📊 Финансовая информационная система",
            bg="#0F172A",
            fg="#E5E7EB",
            font=("Segoe UI Semibold", 20)
        )
        title_lbl.grid(row=0, column=0, sticky="w")

        subtitle_lbl = tk.Label(
            header,
            text="управление счетами и операциями (RUB)",
            bg="#0F172A",
            fg="#9CA3AF",
            font=("Segoe UI", 9)
        )
        subtitle_lbl.grid(row=1, column=0, sticky="w", pady=(0, 8))

        # Основная "карточка" со вкладками
        card = tk.Frame(outer, bg="#111827", bd=0, highlightthickness=0)
        card.grid(row=1, column=0, sticky="nsew")
        card.grid_rowconfigure(0, weight=1)
        card.grid_columnconfigure(0, weight=1)

       
        inner = ttk.Frame(card, padding=6)
        inner.grid(row=0, column=0, sticky="nsew")
        inner.columnconfigure(0, weight=1)
        inner.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(inner)
        notebook.grid(row=0, column=0, sticky="nsew")

        self.page_overview = OverviewPage(notebook, self.store)
        self.page_accounts = AccountsPage(notebook, self.store, on_changed=self._on_data_changed)
        self.page_transactions = TransactionsPage(
            notebook, self.store, on_changed=self._on_data_changed
        )
        self.page_analytics = AnalyticsPage(notebook, self.store)

        notebook.add(self.page_overview, text="Обзор")
        notebook.add(self.page_accounts, text="Счета")
        notebook.add(self.page_transactions, text="Операции")
        notebook.add(self.page_analytics, text="Аналитика")

    def _on_data_changed(self):
        self.page_overview.refresh()
        self.page_accounts.refresh()
        self.page_transactions.refresh()
        self.page_analytics.refresh()


if __name__ == "__main__":
    app = App()
    app.mainloop()