import type { LucideIcon } from "lucide-react";
import {
	AlertCircle,
	ArrowLeft,
	ArrowRight,
	Check,
	Download,
	FileText,
	Inbox,
	LoaderCircle,
	Upload,
	X
} from "lucide-react";
import type { DragEvent, KeyboardEvent, MouseEvent, ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { AnimatedCardReveal, staggerCardDelay } from "./animations/AnimatedCardReveal";
import navLogo from "../assets/logo_nav_bar.png";
import authLogo from "../assets/logo_login_page.png";
import type { NewsStory, PricingBreakdown } from "../types";

export function GradientBackground({ children }: { children: ReactNode }) {
	return (
		<div className="paper-background relative min-h-screen overflow-hidden text-zinc-950">
			<div className="relative z-10">{children}</div>
		</div>
	);
}

export function PublicBackground({ children }: { children: ReactNode }) {
	return (
		<div className="paper-background relative flex min-h-screen flex-col overflow-hidden text-zinc-950">
			<div className="relative z-10 flex min-h-screen flex-col">{children}</div>
		</div>
	);
}

export function EmployeeDashboardBackground({ children }: { children: ReactNode }) {
	return (
		<div className="paper-background relative flex min-h-screen flex-col overflow-hidden text-zinc-950">
			<div className="relative z-10 flex min-h-screen flex-col">{children}</div>
		</div>
	);
}

export function Logo({
	to,
	centered = false,
	size = "nav"
}: {
	to: string;
	centered?: boolean;
	size?: "nav" | "auth";
}) {
	const image = size === "auth" ? authLogo : navLogo;
	const imageClass = size === "auth" ? "h-32 w-auto sm:h-40" : "h-12 w-auto sm:h-14";
	return (
		<Link className={`inline-flex items-center ${centered ? "justify-center" : ""}`} to={to}>
			<img alt="UltraSafe" className={imageClass} src={image} />
		</Link>
	);
}

export function PublicNavbar() {
	return (
		<header className="relative z-50 w-full border-b border-zinc-200/80 bg-white/88 shadow-sm backdrop-blur-xl">
			<div className="mx-auto flex w-full max-w-7xl flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
				<Logo to="/" />
				<nav className="flex w-full flex-wrap gap-2 sm:w-auto sm:justify-end" aria-label="Public navigation">
					{[
						{ label: "Home", to: "/" },
						{ label: "Contact", to: "/contact" },
						{ label: "About", to: "/about" },
						{ label: "Account", to: "/signin" }
					].map((item) => (
						<NavLink
							className={({ isActive }) =>
								`inline-flex min-h-9 flex-1 items-center justify-center rounded-lg px-3 text-sm font-bold transition sm:flex-none ${isActive ? "bg-zinc-950 text-white shadow-sm" : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-950"
								}`
							}
							key={item.to}
							to={item.to}
						>
							{item.label}
						</NavLink>
					))}
				</nav>
			</div>
		</header>
	);
}

export function ClientNavbar() {
	return (
		<header className="w-full border-b border-zinc-200 bg-white/90 shadow-sm backdrop-blur-xl">
			<div className="flex w-full flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
				<Logo to="/client" />
				<nav className="flex w-full flex-wrap gap-2 sm:w-auto sm:justify-end" aria-label="Client navigation">
					{[
						{ label: "Home", to: "/client", end: true },
						{ label: "Quotes", to: "/client/quotes" },
						{ label: "Contracts", to: "/client/contracts" },
						{ label: "Claims", to: "/client/claims" },
						{ label: "Account", to: "/client/account" }
					].map((item) => (
						<NavLink
							className={({ isActive }) =>
								`inline-flex min-h-9 flex-1 items-center justify-center rounded-lg px-3 text-sm font-bold transition sm:flex-none ${isActive ? "bg-zinc-950 text-white shadow-sm" : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-950"
								}`
							}
							end={item.end}
							key={item.to}
							to={item.to}
						>
							{item.label}
						</NavLink>
					))}
				</nav>
			</div>
		</header>
	);
}

export function EmployeeNavbar() {
	return (
		<header className="w-full border-b border-zinc-200 bg-white/90 shadow-sm backdrop-blur-xl">
			<div className="flex w-full flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
				<Logo to="/employee" />
				<nav className="flex w-full flex-wrap gap-2 sm:w-auto sm:justify-end" aria-label="Employee navigation">
					{[
						{ label: "Home", to: "/employee", end: true },
						{ label: "Legal Review", to: "/legal-review" },
						{ label: "Quotes", to: "/employee/quotes" },
						{ label: "Contracts", to: "/employee/contracts" },
						{ label: "Claims", to: "/employee/claims" },
						{ label: "Rules", to: "/employee/rules" },
						{ label: "Account", to: "/employee/account" }
					].map((item) => (
						<NavLink
							className={({ isActive }) =>
								`inline-flex min-h-9 flex-1 items-center justify-center rounded-lg px-3 text-sm font-bold transition sm:flex-none ${isActive ? "bg-zinc-950 text-white shadow-sm" : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-950"
								}`
							}
							end={item.end}
							key={item.to}
							to={item.to}
						>
							{item.label}
						</NavLink>
					))}
				</nav>
			</div>
		</header>
	);
}

const buttonVariants = {
	primary: "bg-zinc-950 text-white shadow-sm hover:bg-zinc-800 focus:ring-zinc-200",
	secondary: "border border-zinc-200 bg-white text-zinc-700 shadow-sm hover:border-zinc-300 hover:bg-zinc-50 focus:ring-zinc-100",
	success: "bg-emerald-600 text-white hover:bg-emerald-700 focus:ring-emerald-100",
	danger: "bg-red-600 text-white hover:bg-red-700 focus:ring-red-100",
	warning: "bg-amber-500 text-white hover:bg-amber-600 focus:ring-amber-100",
	ghost: "text-zinc-600 hover:bg-zinc-100 focus:ring-zinc-100"
};

type CardRevealProps = {
	animated?: boolean;
	revealDelay?: number;
};

export function Button({
	children,
	className = "",
	disabled,
	icon: Icon,
	loading = false,
	onClick,
	type = "button",
	variant = "secondary"
}: {
	children: ReactNode;
	className?: string;
	disabled?: boolean;
	icon?: LucideIcon;
	loading?: boolean;
	onClick?: () => void;
	type?: "button" | "submit" | "reset";
	variant?: keyof typeof buttonVariants;
}) {
	return (
		<button
			className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-bold transition focus:outline-none focus:ring-4 disabled:cursor-not-allowed disabled:opacity-50 ${buttonVariants[variant]} ${className}`}
			disabled={disabled || loading}
			onClick={onClick}
			type={type}
		>
			{loading ? (
				<LoaderCircle className="h-4 w-4 animate-spin" />
			) : Icon ? (
				<Icon className="h-4 w-4" />
			) : null}
			{children}
		</button>
	);
}

export function PageHeader({
	title,
	description,
	action,
	animated = false,
	revealDelay = 0
}: {
	title: string;
	description?: string;
	action?: ReactNode;
	animated?: boolean;
	revealDelay?: number;
}) {
	const headerClassName = "mb-5 rounded-xl border border-zinc-200 bg-white/95 px-4 py-4 text-zinc-950 shadow-sm backdrop-blur sm:px-5";
	const content = (
		<div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
			<div className="min-w-0">
				<p className="mb-1 text-[11px] font-extrabold uppercase tracking-[0.16em] text-orange-600">Workspace</p>
				<h1 className="text-2xl font-extrabold tracking-normal text-zinc-950 sm:text-3xl">{title}</h1>
				{description ? <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-600">{description}</p> : null}
			</div>
			{action ? <div className="flex w-full shrink-0 flex-col gap-2 sm:w-auto sm:flex-row sm:justify-end">{action}</div> : null}
		</div>
	);

	if (animated) {
		return (
			<AnimatedCardReveal className={headerClassName} delay={revealDelay}>
				{content}
			</AnimatedCardReveal>
		);
	}

	return (
		<header className={headerClassName}>
			{content}
		</header>
	);
}

export function Modal({
	open,
	title,
	children,
	actions,
	onClose
}: {
	open: boolean;
	title: string;
	children: ReactNode;
	actions: ReactNode;
	onClose: () => void;
}) {
	if (!open) return null;
	return (
		<div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/45 p-4 backdrop-blur-sm">
			<div className="w-full max-w-lg rounded-xl border border-zinc-200 bg-white p-5 shadow-soft">
				<div className="flex items-start justify-between gap-4">
					<div>
						<div className="mb-3 inline-flex rounded-lg bg-orange-50 p-2 text-orange-600">
							<AlertCircle className="h-5 w-5" />
						</div>
						<h2 className="text-lg font-extrabold text-zinc-950">{title}</h2>
					</div>
					<button className="rounded-lg p-1.5 text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-900 focus:outline-none focus:ring-4 focus:ring-zinc-100" onClick={onClose} type="button">
						<X className="h-5 w-5" />
					</button>
				</div>
				<div className="mt-3 text-sm leading-6 text-zinc-600">{children}</div>
				<div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">{actions}</div>
			</div>
		</div>
	);
}

export function StatusBadge({ status }: { status: string }) {
	const colors: Record<string, string> = {
		draft: "bg-slate-100 text-slate-700 ring-slate-200",
		submitted: "bg-orange-50 text-orange-600 ring-orange-200",
		in_review: "bg-amber-50 text-amber-700 ring-amber-200",
		approved: "bg-emerald-50 text-emerald-700 ring-emerald-200",
		rejected: "bg-red-50 text-red-700 ring-red-200",
		"In Review": "bg-amber-50 text-amber-700 ring-amber-200",
		Draft: "bg-slate-100 text-slate-700 ring-slate-200",
		Accepted: "bg-emerald-50 text-emerald-700 ring-emerald-200",
		Rejected: "bg-red-50 text-red-700 ring-red-200",
		Approved: "bg-emerald-50 text-emerald-700 ring-emerald-200",
		Declined: "bg-red-50 text-red-700 ring-red-200",
		Submitted: "bg-orange-50 text-orange-600 ring-orange-200",
		"Inspection Request": "bg-orange-50 text-orange-700 ring-orange-200",
		Ready: "bg-emerald-50 text-emerald-700 ring-emerald-200",
		"Not ready": "bg-slate-100 text-slate-700 ring-slate-200",
		Issued: "bg-amber-50 text-amber-700 ring-amber-200",
		"Awaiting client signing": "bg-purple-50 text-purple-700 ring-purple-200",
		Signed: "bg-emerald-50 text-emerald-700 ring-emerald-200",
		contract_generated: "bg-purple-50 text-purple-700 ring-purple-200",
		accepted_by_client: "bg-emerald-50 text-emerald-700 ring-emerald-200",
		declined_by_client: "bg-red-50 text-red-700 ring-red-200",
		generated: "bg-purple-50 text-purple-700 ring-purple-200",
		issued: "bg-orange-50 text-orange-600 ring-orange-200",
		active: "bg-emerald-50 text-emerald-700 ring-emerald-200",
		declined: "bg-red-50 text-red-700 ring-red-200",
		accepted: "bg-emerald-50 text-emerald-700 ring-emerald-200",
		inspection_requested: "bg-orange-50 text-orange-700 ring-orange-200",
		paid: "bg-purple-50 text-purple-700 ring-purple-200",
		success: "bg-emerald-50 text-emerald-700 ring-emerald-200",
		Success: "bg-emerald-50 text-emerald-700 ring-emerald-200",
		ready: "bg-emerald-50 text-emerald-700 ring-emerald-200",
		failed: "bg-red-50 text-red-700 ring-red-200",
		Failed: "bg-red-50 text-red-700 ring-red-200"
	};
	return (
		<span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-bold ring-1 ring-inset ${colors[status] ?? colors.draft}`}>
			{titleCase(status)}
		</span>
	);
}

export function ScoreBadge({ score }: { score: number }) {
	const positive = score > 70;
	return (
		<span
			className={`inline-flex rounded-full px-2.5 py-1 text-xs font-bold ring-1 ring-inset ${positive ? "bg-emerald-50 text-emerald-700 ring-emerald-200" : "bg-red-50 text-red-700 ring-red-200"
				}`}
		>
			{score} · {positive ? "Higher review signal" : "Needs verification"}
		</span>
	);
}

export interface DataTableColumn<T> {
	header: string;
	render: (item: T) => ReactNode;
	width?: string;
	headerClassName?: string;
	cellClassName?: string;
}

export interface DataTableProps<T extends { id: string }> extends CardRevealProps {
	columns: Array<DataTableColumn<T>>;
	data: T[];
	emptyText: string;
	getRowHref?: (item: T) => string | undefined;
	className?: string;
	scrollerClassName?: string;
	variant?: "card" | "embedded";
}

export function DataTable<T extends { id: string }>({
	columns,
	data,
	emptyText,
	getRowHref,
	className = "",
	scrollerClassName = "",
	variant = "card",
	animated = false,
	revealDelay = 0
}: DataTableProps<T>) {
	const navigate = useNavigate();
	if (!data.length) return <EmptyState animated={animated} revealDelay={revealDelay} title={emptyText} />;
	const frameClassName = variant === "card"
		? `overflow-hidden rounded-xl border border-zinc-200 bg-white text-zinc-950 shadow-sm ${className}`
		: `overflow-hidden text-zinc-950 ${className}`;

	function rowHref(item: T) {
		return getRowHref?.(item);
	}

	function navigateToRow(item: T, event?: MouseEvent<HTMLTableRowElement> | KeyboardEvent<HTMLTableRowElement>) {
		const href = rowHref(item);
		if (!href) return;
		if (event && isInteractiveEventTarget(event.target)) return;
		navigate(href);
	}

	function handleRowKeyDown(item: T, event: KeyboardEvent<HTMLTableRowElement>) {
		if (event.target !== event.currentTarget) return;
		if (event.key !== "Enter" && event.key !== " ") return;
		event.preventDefault();
		navigateToRow(item);
	}

	function rowClassName(hasHref: boolean) {
		return [
			"group transition-colors",
			hasHref
				? "cursor-pointer hover:bg-zinc-50 focus:bg-zinc-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-orange-100"
				: "hover:bg-zinc-50"
		].join(" ");
	}

	function headerCellClassName(column: DataTableColumn<T>) {
		const isAction = isActionColumn(column);
		return [
			"px-3 py-2.5 text-left text-[11px] font-extrabold uppercase tracking-[0.08em] text-zinc-500",
			isAction ? "sticky right-0 z-30 bg-zinc-50 shadow-[-12px_0_18px_-18px_rgba(24,24,27,0.45)]" : "",
			column.headerClassName ?? ""
		].join(" ");
	}

	function bodyCellClassName(column: DataTableColumn<T>, hasHref: boolean) {
		const isAction = isActionColumn(column);
		return [
			"whitespace-nowrap px-3 py-3 text-sm text-zinc-700",
			isAction
				? `sticky right-0 z-20 bg-white shadow-[-12px_0_18px_-18px_rgba(24,24,27,0.45)] ${hasHref ? "group-hover:bg-zinc-50 group-focus:bg-zinc-50" : "group-hover:bg-zinc-50"}`
				: "",
			column.cellClassName ?? ""
		].join(" ");
	}

	function renderFrame(children: ReactNode) {
		if (animated && variant === "card") {
			return (
				<AnimatedCardReveal className={frameClassName} delay={revealDelay}>
					{children}
				</AnimatedCardReveal>
			);
		}
		return <div className={frameClassName}>{children}</div>;
	}

	if (scrollerClassName) {
		return renderFrame(
				<div className={`overflow-x-auto overflow-y-scroll [scrollbar-gutter:stable] ${scrollerClassName}`}>
					<table className="min-w-full table-fixed divide-y divide-zinc-200">
						<colgroup>
							{columns.map((column) => (
								<col key={column.header} style={column.width ? { width: column.width } : undefined} />
							))}
						</colgroup>
						<thead className="sticky top-0 z-10 bg-zinc-50 shadow-[0_1px_0_rgba(228,228,231,1)]">
							<tr>
								{columns.map((column) => (
									<th className={headerCellClassName(column)} key={column.header}>
										{column.header}
									</th>
								))}
							</tr>
						</thead>
						<tbody className="divide-y divide-zinc-100">
							{data.map((item) => {
								const href = rowHref(item);
								return (
									<tr
										aria-label={href ? `Open row ${item.id}` : undefined}
										className={rowClassName(Boolean(href))}
										key={item.id}
										onClick={href ? (event) => navigateToRow(item, event) : undefined}
										onKeyDown={href ? (event) => handleRowKeyDown(item, event) : undefined}
										role={href ? "link" : undefined}
										tabIndex={href ? 0 : undefined}
									>
										{columns.map((column) => (
											<td className={bodyCellClassName(column, Boolean(href))} key={column.header}>
												{column.render(item)}
											</td>
										))}
									</tr>
								);
							})}
						</tbody>
					</table>
				</div>
		);
	}
	return renderFrame(
			<div className={`overflow-x-auto ${scrollerClassName}`}>
				<table className="min-w-full divide-y divide-zinc-200">
					<colgroup>
						{columns.map((column) => (
							<col key={column.header} style={column.width ? { width: column.width } : undefined} />
						))}
					</colgroup>
					<thead className="bg-zinc-50">
						<tr>
							{columns.map((column) => (
								<th className={headerCellClassName(column)} key={column.header}>
									{column.header}
								</th>
							))}
						</tr>
					</thead>
					<tbody className="divide-y divide-zinc-100">
						{data.map((item) => {
							const href = rowHref(item);
							return (
								<tr
									aria-label={href ? `Open row ${item.id}` : undefined}
									className={rowClassName(Boolean(href))}
									key={item.id}
									onClick={href ? (event) => navigateToRow(item, event) : undefined}
									onKeyDown={href ? (event) => handleRowKeyDown(item, event) : undefined}
									role={href ? "link" : undefined}
									tabIndex={href ? 0 : undefined}
								>
									{columns.map((column) => (
										<td className={bodyCellClassName(column, Boolean(href))} key={column.header}>
											{column.render(item)}
										</td>
									))}
								</tr>
							);
						})}
					</tbody>
				</table>
			</div>
	);
}

function isActionColumn<T>(column: DataTableColumn<T>) {
	return column.header.toLowerCase() === "action" || column.header.toLowerCase() === "actions";
}

function isInteractiveEventTarget(target: EventTarget | null) {
	if (!(target instanceof Element)) return false;
	return Boolean(
		target.closest("a, button, input, select, textarea, label, summary, [role='button'], [data-row-click-ignore='true']")
	);
}

export type UploadCardFile = {
	file_name: string;
	content_type?: string;
	size_bytes?: number;
	needs_reselect?: boolean;
};

export function UploadCard({
	label,
	optional,
	fileName,
	displayFiles = [],
	selectedFiles = [],
	disabled = false,
	multiple = false,
	size = "default",
	onUpload,
	onFilesSelected,
	onRemoveFile,
	animated = false,
	revealDelay = 0
}: {
	label: string;
	optional?: boolean;
	fileName?: string;
	displayFiles?: UploadCardFile[];
	selectedFiles?: File[];
	disabled?: boolean;
	multiple?: boolean;
	size?: "default" | "compact";
	onUpload?: (fileName: string) => void;
	onFilesSelected?: (files: File[]) => void;
	onRemoveFile?: (index: number) => void;
} & CardRevealProps) {
	const inputRef = useRef<HTMLInputElement | null>(null);
	const [isDragging, setIsDragging] = useState(false);
	const filesToShow = selectedFiles.length
		? selectedFiles.map(fileToUploadCardFile)
		: displayFiles.length
			? displayFiles
			: fileName
				? [{ file_name: fileName }]
				: [];
	const hasFiles = filesToShow.length > 0;

	function selectFiles(files: File[]) {
		if (disabled || !files.length) return;
		const nextFiles = multiple ? files : files.slice(0, 1);
		onFilesSelected?.(nextFiles);
		onUpload?.(nextFiles.map((file) => file.name).join(", "));
	}

	function handleInputChange() {
		const files = Array.from(inputRef.current?.files ?? []);
		selectFiles(files);
		if (inputRef.current) inputRef.current.value = "";
	}

	function handleDragOver(event: DragEvent<HTMLDivElement>) {
		if (disabled) return;
		event.preventDefault();
		setIsDragging(true);
	}

	function handleDragLeave() {
		setIsDragging(false);
	}

	function handleDrop(event: DragEvent<HTMLDivElement>) {
		if (disabled) return;
		event.preventDefault();
		setIsDragging(false);
		selectFiles(Array.from(event.dataTransfer.files));
	}

	const compact = size === "compact";
	const cardClassName = `flex ${compact ? "min-h-20" : "min-h-32"} flex-col items-center justify-center rounded-xl border border-dashed ${compact ? "p-2" : "p-3"} text-center transition ${disabled
		? "border-slate-200 bg-slate-50 opacity-70"
		: isDragging
			? "border-slate-500 bg-slate-50"
			: "border-slate-300 bg-white hover:border-slate-400 hover:bg-slate-50"
		}`;
	const sharedCardProps = {
		className: cardClassName,
		onDragLeave: handleDragLeave,
		onDragOver: handleDragOver,
		onDrop: handleDrop
	};
	const cardBody = (
		<>
			<input
				accept=".pdf,.docx,.jpg,.jpeg,.png,application/pdf,image/png,image/jpeg,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
				className="hidden"
				disabled={disabled}
				multiple={multiple}
				onChange={handleInputChange}
				ref={inputRef}
				type="file"
			/>
			<Upload className={`${compact ? "h-4 w-4" : "h-5 w-5"} ${disabled ? "text-slate-400" : "text-slate-600"}`} />
			<span className={`${compact ? "mt-1 text-xs" : "mt-2 text-sm"} font-bold ${disabled ? "text-slate-500" : "text-slate-800"}`}>{label}</span>
			<span className={`${compact ? "mt-0.5 text-[11px]" : "mt-1 text-xs"} text-slate-500`}>{optional ? "Optional" : "PDF, DOCX, JPG, PNG"}</span>
			<button
				className={`${compact ? "mt-2 px-2.5 py-1" : "mt-3 px-3 py-1.5"} rounded-md border border-slate-200 bg-white text-xs font-bold text-slate-700 shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400`}
				disabled={disabled}
				onClick={() => inputRef.current?.click()}
				type="button"
			>
				Choose file{multiple ? "s" : ""}
			</button>
			{hasFiles ? (
				<div className={`${compact ? "mt-2 space-y-1" : "mt-3 space-y-2"} w-full`}>
					{filesToShow.map((file, index) => (
						<div className={`rounded-md bg-emerald-50 px-2 ${compact ? "py-1" : "py-1.5"} text-left`} key={`${file.file_name}-${index}`}>
							<div className="flex items-start justify-between gap-2">
								<div className="min-w-0">
									<p className="truncate text-xs font-bold text-emerald-800">{file.file_name}</p>
									<p className="mt-0.5 text-[11px] font-semibold text-emerald-700">
										{formatUploadFileMeta(file)}
									</p>
									{file.needs_reselect ? (
										<p className="mt-0.5 text-[11px] font-semibold text-amber-700">Reselect before submit</p>
									) : null}
								</div>
								{onRemoveFile && !disabled ? (
									<button
										aria-label={`Remove ${file.file_name}`}
										className="rounded-full p-1 text-emerald-700 hover:bg-emerald-100"
										onClick={() => onRemoveFile(index)}
										type="button"
									>
										<X className="h-3.5 w-3.5" />
									</button>
								) : null}
							</div>
						</div>
					))}
				</div>
			) : null}
		</>
	);

	if (animated) {
		return (
			<AnimatedCardReveal {...sharedCardProps} delay={revealDelay}>
				{cardBody}
			</AnimatedCardReveal>
		);
	}

	return (
		<div {...sharedCardProps}>
			{cardBody}
		</div>
	);
}

function fileToUploadCardFile(file: File): UploadCardFile {
	return {
		file_name: file.name,
		content_type: file.type,
		size_bytes: file.size
	};
}

function formatUploadFileMeta(file: UploadCardFile) {
	const parts = [
		file.content_type || "Unknown type",
		typeof file.size_bytes === "number" ? formatFileSize(file.size_bytes) : null
	].filter(Boolean);
	return parts.join(" · ");
}

function formatFileSize(sizeBytes: number) {
	if (sizeBytes < 1024) return `${sizeBytes} B`;
	if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`;
	return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function Stepper({
	steps,
	active
}: {
	steps: string[];
	active: number;
}) {
	return (
		<div className="grid gap-1.5 sm:grid-cols-3 lg:grid-cols-6 xl:grid-cols-10">
			{steps.map((step, index) => (
				<div
					className={`rounded-xl border px-2.5 py-2 text-xs font-semibold ${index === active
						? "border-orange-200 bg-orange-50 text-orange-600"
						: index < active
							? "border-emerald-200 bg-emerald-50 text-emerald-700"
							: "border-slate-200 bg-white text-slate-500"
						}`}
					key={step}
				>
					<span className="mr-1.5 inline-flex h-5 w-5 items-center justify-center rounded-full bg-white text-[11px] shadow-sm">
						{index < active ? <Check className="h-3.5 w-3.5" /> : index + 1}
					</span>
					{step}
				</div>
			))}
		</div>
	);
}

export function PremiumCounter({
	value,
	breakdown,
	animated = false,
	revealDelay = 0
}: {
	value: number;
	breakdown?: PricingBreakdown;
} & CardRevealProps) {
	const [display, setDisplay] = useState(value);

	useEffect(() => {
		const start = display;
		const delta = value - start;
		const started = performance.now();
		const frame = window.setInterval(() => {
			const progress = Math.min((performance.now() - started) / 450, 1);
			setDisplay(Math.round(start + delta * progress));
			if (progress === 1) window.clearInterval(frame);
		}, 16);
		return () => window.clearInterval(frame);
	}, [value]);

	const adjustments = breakdown?.adjustments ?? [];
	const finalPreview = breakdown?.estimatedPremium ?? breakdown?.finalPremium ?? value;
	const receiptRows = breakdown ? premiumReceiptRows(breakdown, adjustments) : [];
	const className = "rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5";

	const content = (
		<>
				<div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
					<div className="min-w-0 lg:flex-1">
						<p className="text-xl font-bold tracking-normal text-slate-950 sm:text-2xl">
							Annual Premium Estimate
						</p>
					<p className="mt-1 text-3xl font-bold tracking-normal text-orange-600 sm:text-4xl">
						{formatCurrency(display)}
					</p>
				</div>
				{breakdown ? (
					<div className="w-full rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs font-semibold text-slate-600 lg:w-[460px] lg:shrink-0">
						<div className="flex items-center justify-between gap-4 pb-1.5">
							<span>Base from coverage</span>
							<span className="text-right tabular-nums text-slate-900">{formatCurrency(breakdown.basePremium)}</span>
						</div>
						<div className="space-y-1.5">
							{receiptRows.map((row) => (
								<div className="flex items-center justify-between gap-4" key={row.label}>
									<span>{row.label}</span>
									<span className={`text-right tabular-nums ${premiumDeltaClass(row.amount)}`}>
										{formatSignedCurrency(row.amount)}
									</span>
								</div>
							))}
							</div>
							<div className="mt-2 flex items-center justify-between gap-4 border-t border-slate-200 pt-2 text-slate-900">
								<span>Preview estimate</span>
								<span className="text-right tabular-nums">{formatCurrency(finalPreview)}</span>
							</div>
					</div>
				) : null}
			</div>
		</>
	);

	if (animated) {
		return (
			<AnimatedCardReveal className={className} delay={revealDelay}>
				{content}
			</AnimatedCardReveal>
		);
	}

	return (
		<div className={className}>
			{content}
		</div>
	);
}

function premiumReceiptRows(
	breakdown: PricingBreakdown,
	adjustments: NonNullable<PricingBreakdown["adjustments"]>
) {
	const amountFor = (code: string) =>
		adjustments
			.filter((adjustment) => adjustment.code === code)
			.reduce((total, adjustment) => total + adjustment.amountDelta, 0);
	const rows = [
		{ label: "Property type adjustment", amount: amountFor("property_type") },
		{ label: "Property age adjustment", amount: amountFor("property_age") },
		{ label: "Property size adjustment", amount: amountFor("property_size") },
		{ label: "Construction adjustment", amount: amountFor("construction") },
		{ label: "Claims history adjustment", amount: amountFor("claims_history") },
		{ label: "Claims surcharge", amount: breakdown.manualReviewSurcharge }
	];
	const optionalRows = [
		{ label: "Use adjustment", amount: amountFor("property_use") },
		{ label: "Security adjustment", amount: amountFor("security") }
	].filter((row) => row.amount !== 0);

	return [...rows, ...optionalRows];
}

function premiumDeltaClass(value: number) {
	if (value < 0) return "text-emerald-700";
	if (value > 0) return "text-orange-600";
	return "text-slate-500";
}

export function DocumentTextViewer({
	text,
	title = "Contract document"
}: {
	text?: string | null;
	title?: string;
}) {
	const displayText = normalizeDocumentListBullets(text);

	return (
		<Panel className="flex h-full flex-col lg:h-[740px]">
			<div className="mb-3 flex flex-col gap-1 border-b border-slate-100 pb-3">
				<p className="text-xs font-bold uppercase tracking-[0.12em] text-orange-600">
					UltraSafe Contract Document
				</p>
				<h2 className="text-sm font-bold text-slate-950">{title}</h2>
			</div>
			<div className="min-h-0 flex-1 overflow-y-auto rounded-lg border border-slate-200 bg-slate-100 p-2 shadow-inner">
				<article className="mx-auto min-h-[620px] w-full max-w-5xl rounded-sm bg-white px-5 py-6 text-[13px] leading-6 text-slate-900 shadow-[0_18px_45px_rgba(15,23,42,0.12)] sm:px-8">
					{displayText.trim() ? (
						<ContractDocumentText text={displayText} />
					) : (
						<div className="flex min-h-[420px] items-center justify-center text-center">
							<div>
								<FileText className="mx-auto h-8 w-8 text-slate-300" />
								<p className="mt-3 text-sm font-bold text-slate-700">No generated contract document yet.</p>
								<p className="mt-1 text-xs font-semibold text-slate-500">
									Awaiting generated contract text.
								</p>
							</div>
						</div>
					)}
				</article>
			</div>
		</Panel>
	);
}

function ContractDocumentText({ text }: { text: string }) {
	return (
		<div className="font-sans text-[13px] leading-6 text-slate-900">
			{text.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n").map(renderContractDocumentLine)}
		</div>
	);
}

function renderContractDocumentLine(line: string, index: number) {
	const trimmed = line.trim();
	const key = `${index}-${trimmed || "blank"}`;
	if (!trimmed) return <div aria-hidden="true" className="h-3" key={key} />;
	if (isCenteredContractTitle(trimmed)) {
		return (
			<p className="text-center text-base font-extrabold uppercase tracking-normal text-slate-950" key={key}>
				{trimmed}
			</p>
		);
	}
	if (isContractChapterHeading(trimmed)) {
		return (
			<p className="mt-5 text-sm font-extrabold uppercase tracking-normal text-slate-950" key={key}>
				{trimmed}
			</p>
		);
	}
	if (isContractArticleHeading(trimmed)) {
		return (
			<p className="mt-3 font-bold text-slate-950" key={key}>
				{trimmed}
			</p>
		);
	}
	if (trimmed.startsWith("• ")) {
		return (
			<p className="flex gap-2" key={key}>
				<span aria-hidden="true" className="shrink-0 text-slate-950">•</span>
				<span className="min-w-0">{trimmed.slice(2)}</span>
			</p>
		);
	}
	return (
		<p className="whitespace-pre-wrap break-words" key={key}>
			{line}
		</p>
	);
}

function isCenteredContractTitle(value: string) {
	const normalized = normalizeContractHeading(value);
	return (
		normalized === "POLITA DE ASIGURARE A LOCUINTEI SI BUNURILOR" ||
		normalized === "LOCUINTA SI BUNURI"
	);
}

function isContractChapterHeading(value: string) {
	return /^CAPITOLUL\s+[IVXLCDM]+\b/i.test(value.trim());
}

function isContractArticleHeading(value: string) {
	return /^Art\.\s+\d+\b/i.test(value.trim());
}

function normalizeContractHeading(value: string) {
	return value
		.normalize("NFD")
		.replace(/[\u0300-\u036f]/g, "")
		.toUpperCase();
}

function normalizeDocumentListBullets(text?: string | null) {
	return normalizeDocumentCoverageTable(text ?? "").replace(/(^|\n)([ \t]*)\* /g, "$1$2\u2022 ");
}

function normalizeDocumentCoverageTable(text: string) {
	const normalizedText = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
	return normalizedText.replace(
		/^[ \t]*\|\s*Categoria\s*\|[^\n]*\|\s*$\n^[ \t]*\|\s*-+\s*\|\s*-+\s*\|\s*$\n^[ \t]*\|\s*Locuin[^|]*\|\s*([^|\n]+?)\s*\|\s*$\n^[ \t]*\|\s*Bunuri mobile\s*\|\s*([^|\n]+?)\s*\|\s*$\n^[ \t]*\|\s*Total\s*\|\s*([^|\n]+?)\s*\|/gim,
		(_, buildingAmount: string, contentsAmount: string, totalAmount: string) => (
			`Suma asigurată totală este de ${totalAmount.trim()}.\n\n` +
			`Aceasta este compusă din:\n` +
			`• suma asigurată pentru locuință: ${buildingAmount.trim()};\n` +
			`• suma asigurată pentru bunuri mobile: ${contentsAmount.trim()}.`
		)
	);
}

export function NewsList({
	stories,
	selectedId,
	onSelect
}: {
	stories: NewsStory[];
	selectedId?: string;
	onSelect: (story: NewsStory) => void;
}) {
	return (
		<div className="h-[68vh] overflow-y-auto rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
			<h2 className="text-lg font-bold text-slate-950">Intelligence Events</h2>
			<div className="mt-3 divide-y divide-slate-100">
				{!stories.length ? (
					<p className="py-4 text-sm font-semibold text-slate-500">
						No classified intelligence events are available yet.
					</p>
				) : null}
				{stories.map((story) => (
					<button
						className={`w-full py-3 text-left ${selectedId === story.id ? "text-orange-600" : "text-slate-950"}`}
						key={story.id}
						onClick={() => onSelect(story)}
						type="button"
					>
						<h3 className="text-base font-bold leading-6">{story.title}</h3>
						<p className="mt-2 text-xs font-semibold text-slate-500">
							{story.sourceName ?? story.coverageLabel}
							{story.relevance ? ` · Relevance: ${story.relevance}` : ""}
						</p>
					</button>
				))}
			</div>
		</div>
	);
}

export function NewsArticle({ story }: { story?: NewsStory }) {
	if (!story) {
		return (
			<EmptyState
				description="Stay up to date with news that may be relevant for underwriting."
				title="Select a news story to view"
			/>
		);
	}
	return (
		<article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
			<p className="text-xs font-bold uppercase text-slate-500">Published {story.publishedAt}</p>
			<h1 className="mt-2 text-2xl font-bold tracking-normal text-slate-950">{story.title}</h1>
			<div className="mt-3 flex flex-wrap gap-2 text-xs font-bold">
				{story.country ? <EventPill tone="slate" label="Country" value={countryLabel(story.country)} /> : null}
				{story.lineOfBusiness ? (
					<EventPill tone="blue" label="Domain" value={story.lineOfBusiness} />
				) : null}
				{story.relevance ? <EventPill tone="slate" label="Relevance" value={story.relevance} /> : null}
				{story.severity ? <EventPill tone="amber" label="Severity" value={story.severity} /> : null}
				{story.eventType ? <EventPill tone="blue" label="Type" value={story.eventType} /> : null}
				{story.topics?.map((topic) => (
					<EventPill tone="slate" label="Topic" value={topic} key={topic} />
				))}
			</div>
			<ul className="mt-4 space-y-2 text-sm leading-5 text-slate-700">
				{story.summary.map((item) => (
					<li className="flex gap-2" key={item}>
						<span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-orange-600" />
						{item}
					</li>
				))}
			</ul>
			{story.sourceLinks?.length ? (
				<div className="mt-5 border-t border-slate-100 pt-4">
					<p className="text-sm font-bold text-slate-900">Sources</p>
					<div className="mt-2 flex flex-wrap gap-2">
						{story.sourceLinks.map((link) => (
							<a
								className="rounded-md border border-slate-200 px-2.5 py-1 text-sm font-semibold text-orange-600 hover:bg-orange-50"
								href={link.url}
								key={link.url}
								rel="noreferrer"
								target="_blank"
							>
								{link.label}
							</a>
						))}
					</div>
				</div>
			) : null}
		</article>
	);
}

function EventPill({
	label,
	value,
	tone
}: {
	label: string;
	value: string;
	tone: "amber" | "blue" | "slate";
}) {
	const colors = {
		amber: "bg-amber-50 text-amber-700",
		blue: "bg-orange-50 text-orange-600",
		slate: "bg-slate-100 text-slate-700"
	};
	return (
		<span className={`rounded-full px-2 py-1 ${colors[tone]}`}>
			{label}: {titleCase(value)}
		</span>
	);
}

function countryLabel(country: string) {
	if (country === "RO") return "Romania";
	return country;
}

export function RulesTable({ headers, rows }: { headers: string[]; rows: string[][] }) {
	return (
		<div className="overflow-hidden rounded-lg border border-slate-200">
			<table className="min-w-full divide-y divide-slate-200 text-sm">
				<thead className="bg-slate-50">
					<tr>
						{headers.map((header) => (
							<th className="px-3 py-2 text-left font-bold text-slate-600" key={header}>
								{header}
							</th>
						))}
					</tr>
				</thead>
				<tbody className="divide-y divide-slate-100 bg-white">
					{rows.map((row) => (
						<tr key={row.join("-")}>
							{row.map((cell) => (
								<td className="px-3 py-2 text-slate-700" key={cell}>
									{cell}
								</td>
							))}
						</tr>
					))}
				</tbody>
			</table>
		</div>
	);
}

export function EmptyState({
	title,
	description,
	animated = false,
	revealDelay = 0
}: { title: string; description?: string } & CardRevealProps) {
	const className = "flex min-h-40 flex-col items-center justify-center rounded-xl border border-dashed border-zinc-300 bg-white/95 p-5 text-center text-zinc-950 shadow-sm";
	const content = (
		<>
			<Inbox className="h-7 w-7 text-orange-500" />
			<h3 className="mt-3 text-base font-extrabold text-zinc-950">{title}</h3>
			{description ? <p className="mt-1 max-w-md text-sm leading-6 text-zinc-600">{description}</p> : null}
		</>
	);

	if (animated) {
		return (
			<AnimatedCardReveal className={className} delay={revealDelay}>
				{content}
			</AnimatedCardReveal>
		);
	}

	return (
		<div className={className}>
			{content}
		</div>
	);
}

export function DetailGrid({
	items,
	animated = false,
	revealDelay = 0
}: { items: Array<[string, ReactNode]> } & CardRevealProps) {
	return (
		<dl className="grid gap-2.5 sm:grid-cols-2">
			{items.map(([label, value], index) => {
				const content = (
					<>
						<dt className="text-[11px] font-extrabold uppercase tracking-[0.08em] text-zinc-500">{label}</dt>
						<dd className="mt-1 text-sm font-bold text-zinc-900">{value}</dd>
					</>
				);
				const className = "rounded-lg border border-zinc-200 bg-zinc-50 p-3";
				return animated ? (
					<AnimatedCardReveal className={className} delay={revealDelay + staggerCardDelay(index)} key={label}>
						{content}
					</AnimatedCardReveal>
				) : (
					<div className={className} key={label}>
						{content}
					</div>
				);
			})}
		</dl>
	);
}

export function Panel({
	children,
	className = "",
	animated = false,
	revealDelay = 0
}: { children: ReactNode; className?: string } & CardRevealProps) {
	const panelClassName = `rounded-xl border border-zinc-200 bg-white/95 p-4 text-zinc-950 shadow-sm backdrop-blur sm:p-5 ${className}`;
	if (animated) {
		return (
			<AnimatedCardReveal className={panelClassName} delay={revealDelay}>
				{children}
			</AnimatedCardReveal>
		);
	}

	return (
		<section className={panelClassName}>
			{children}
		</section>
	);
}

export function BackLink({ to, label = "Back" }: { to: string; label?: string }) {
	return (
		<Link className="inline-flex items-center gap-2 text-sm font-extrabold text-orange-600 hover:text-orange-700" to={to}>
			<ArrowLeft className="h-4 w-4" />
			{label}
		</Link>
	);
}

export function PrimaryLink({ to, children }: { to: string; children: ReactNode }) {
	return (
		<Link className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-zinc-950 px-4 py-2 text-sm font-bold text-white shadow-sm transition hover:bg-zinc-800 focus:outline-none focus:ring-4 focus:ring-zinc-200" to={to}>
			{children}
			<ArrowRight className="h-4 w-4" />
		</Link>
	);
}

export function MockDownloadButton({ onClick }: { onClick: () => void }) {
	return (
		<Button icon={Download} onClick={onClick} variant="primary">
			Download
		</Button>
	);
}

export function MockDocumentItem({
	name,
	url,
	contentType,
	sizeBytes
}: {
	name: string;
	url?: string;
	contentType?: string;
	sizeBytes?: number;
}) {
	const canOpen = Boolean(url);
	return (
		<button
			className={`inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-semibold shadow-sm ${canOpen
				? "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
				: "cursor-not-allowed border-slate-200 bg-slate-50 text-slate-400"
				}`}
			disabled={!canOpen}
			onClick={() => {
				if (url) window.open(url, "_blank", "noopener,noreferrer");
			}}
			title={canOpen ? name : "Document link unavailable"}
			type="button"
		>
			<FileText className={`h-4 w-4 ${canOpen ? "text-orange-600" : "text-slate-400"}`} />
			<span className="text-left">
				<span className="block">{name}</span>
				{contentType || typeof sizeBytes === "number" ? (
					<span className="block text-xs font-semibold text-slate-500">
						{[
							contentType,
							typeof sizeBytes === "number" ? formatFileSize(sizeBytes) : null
						].filter(Boolean).join(" · ")}
					</span>
				) : !canOpen ? (
					<span className="block text-xs font-semibold text-slate-500">Unavailable</span>
				) : null}
			</span>
		</button>
	);
}

export function formatCurrency(value: number) {
	return new Intl.NumberFormat("ro-RO", {
		style: "currency",
		currency: "RON",
		maximumFractionDigits: 0
	}).format(value || 0);
}

function formatSignedCurrency(value: number) {
	if (!value) return formatCurrency(0);
	const sign = value > 0 ? "+" : "-";
	return `${sign}${formatCurrency(Math.abs(value))}`;
}

export function formatDate(value: string) {
	return new Intl.DateTimeFormat("en-GB", {
		day: "2-digit",
		month: "short",
		year: "numeric"
	}).format(new Date(value));
}

export function titleCase(value: string) {
	return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
