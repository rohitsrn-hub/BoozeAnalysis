import { useTheme } from "next-themes"
import { Toaster as Sonner, toast } from "sonner"

/**
* Renders a themed Sonner toast provider with customizable props.
* @example
* Toaster({ duration: 3000 })
* // Renders a Sonner component with light theme and custom duration.
* @param {Object} props - Additional properties to pass to the Sonner component.
* @returns {JSX.Element} The rendered Sonner toast provider component.
**/
const Toaster = ({
  ...props
}) => {
  const { theme = "system" } = useTheme()

  return (
    <Sonner
      theme={theme}
      className="toaster group"
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:bg-background group-[.toaster]:text-foreground group-[.toaster]:border-border group-[.toaster]:shadow-lg",
          description: "group-[.toast]:text-muted-foreground",
          actionButton:
            "group-[.toast]:bg-primary group-[.toast]:text-primary-foreground",
          cancelButton:
            "group-[.toast]:bg-muted group-[.toast]:text-muted-foreground",
        },
      }}
      {...props} />
  );
}

export { Toaster, toast }
