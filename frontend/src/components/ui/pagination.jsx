import * as React from "react"
import { ChevronLeft, ChevronRight, MoreHorizontal } from "lucide-react"

import { cn } from "@/lib/utils"
import { buttonVariants } from "@/components/ui/button";

const Pagination = ({
  className,
  ...props
}) => (
  <nav
    role="navigation"
    aria-label="pagination"
    className={cn("mx-auto flex w-full justify-center", className)}
    {...props} />
)
Pagination.displayName = "Pagination"

const PaginationContent = React.forwardRef(({ className, ...props }, ref) => (
  <ul
    ref={ref}
    className={cn("flex flex-row items-center gap-1", className)}
    {...props} />
))
PaginationContent.displayName = "PaginationContent"

const PaginationItem = React.forwardRef(({ className, ...props }, ref) => (
  <li ref={ref} className={cn("", className)} {...props} />
))
PaginationItem.displayName = "PaginationItem"

/**
* Renders a styled pagination link that reflects its active state.
* @example
* PaginationLink("custom-class", true, "icon")
* <a aria-current="page" class="..." />
* @param {{string}} {{className}} - Additional CSS class names for custom styling.
* @param {{boolean}} {{isActive}} - Indicates if the link corresponds to the current page.
* @param {{"icon"|"sm"|"md"|"lg"}} {{size}} - Size variant of the button, defaults to "icon".
* @param {{Object}} {{props}} - Extra props forwarded to the underlying anchor element.
* @returns {{JSX.Element}} A fully-styled anchor element representing a pagination link.
**/
const PaginationLink = ({
  className,
  isActive,
  size = "icon",
  ...props
}) => (
  <a
    aria-current={isActive ? "page" : undefined}
    className={cn(buttonVariants({
      variant: isActive ? "outline" : "ghost",
      size,
    }), className)}
    {...props} />
)
PaginationLink.displayName = "PaginationLink"

/**
* Renders a pagination link that navigates to the previous page.
* @example
* PaginationPrevious("custom-class", { href: "/page/1" })
* <a aria-label="Go to previous page" class="gap-1 pl-2.5 custom-class"><svg>…</svg><span>Previous</span></a>
* @param {string} [className] - Additional CSS class names to apply.
* @param {object} props - Additional props forwarded to the underlying PaginationLink component.
* @returns {JSX.Element} A JSX element representing the "Previous" pagination control.
**/
const PaginationPrevious = ({
  className,
  ...props
}) => (
  <PaginationLink
    aria-label="Go to previous page"
    size="default"
    className={cn("gap-1 pl-2.5", className)}
    {...props}>
    <ChevronLeft className="h-4 w-4" />
    <span>Previous</span>
  </PaginationLink>
)
PaginationPrevious.displayName = "PaginationPrevious"

/**
* React component that renders a pagination link leading to the next page.
* @example
* PaginationNext({ className: "text-blue-500", href: "/page/2" })
* <a aria-label="Go to next page">Next ›</a>
* @param {string} className - Additional CSS classes for the link element.
* @param {Object} props - Extra props forwarded to the underlying PaginationLink component.
* @returns {JSX.Element} The rendered "Next" pagination link element.
**/
const PaginationNext = ({
  className,
  ...props
}) => (
  <PaginationLink
    aria-label="Go to next page"
    size="default"
    className={cn("gap-1 pr-2.5", className)}
    {...props}>
    <span>Next</span>
    <ChevronRight className="h-4 w-4" />
  </PaginationLink>
)
PaginationNext.displayName = "PaginationNext"

/**
* React component that renders an ellipsis pagination control in a span element.
* @example
* <MorePaginationButton className="my-class" aria-label="Open more pages" />
* // <span ...>…</span>
* @param {string} className - Optional additional Tailwind CSS classes to apply.
* @param {object} props - Additional HTML attributes spread onto the span element.
* @returns {JSX.Element} A span element representing the “more pages” pagination button.
**/
const PaginationEllipsis = ({
  className,
  ...props
}) => (
  <span
    aria-hidden
    className={cn("flex h-9 w-9 items-center justify-center", className)}
    {...props}>
    <MoreHorizontal className="h-4 w-4" />
    <span className="sr-only">More pages</span>
  </span>
)
PaginationEllipsis.displayName = "PaginationEllipsis"

export {
  Pagination,
  PaginationContent,
  PaginationLink,
  PaginationItem,
  PaginationPrevious,
  PaginationNext,
  PaginationEllipsis,
}
