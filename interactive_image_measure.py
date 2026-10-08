import csv
import math
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from PIL import Image


class ImageMeasureTool:
    def __init__(self, image_path):
        self.image_path = Path(image_path)
        self.calibration_points = []
        self.points = []
        self.artists = []
        self.calibration_artists = []
        self.mm_per_pixel = None
        self.straighten_points = []
        self.straighten_mode = False

        self.image = Image.open(self.image_path)
        self.figure, self.ax = plt.subplots(figsize=(12, 8))
        self.figure.canvas.manager.set_window_title("Interactive mm measurement")
        self.ax.imshow(self.image)
        self.ax.set_xlabel("X (pixels)")
        self.ax.set_ylabel("Y (pixels)")

        straighten_axis = self.figure.add_axes((0.20, 0.01, 0.16, 0.045))
        reset_axis = self.figure.add_axes((0.38, 0.01, 0.13, 0.045))
        clear_axis = self.figure.add_axes((0.53, 0.01, 0.11, 0.045))
        undo_axis = self.figure.add_axes((0.66, 0.01, 0.09, 0.045))
        save_axis = self.figure.add_axes((0.77, 0.01, 0.11, 0.045))
        self.save_button = Button(save_axis, "Save CSV")
        self.undo_button = Button(undo_axis, "Undo")
        self.clear_button = Button(clear_axis, "Clear points")
        self.reset_button = Button(reset_axis, "Reset calibration")
        self.straighten_button = Button(straighten_axis, "Straighten image")
        self.save_button.on_clicked(self.save_csv)
        self.undo_button.on_clicked(self.undo_last)
        self.clear_button.on_clicked(self.clear_points)
        self.reset_button.on_clicked(self.reset_calibration)
        self.straighten_button.on_clicked(self.start_straightening)
        self.figure.canvas.mpl_connect("button_press_event", self.on_click)
        self.update_title()

    def update_title(self):
        if self.straighten_mode:
            self.ax.set_title(
                "Straighten image: click two points along a reference edge"
            )
        elif self.mm_per_pixel is None:
            self.ax.set_title(
                "Calibration: click both endpoints of a known reference length"
            )
        else:
            self.ax.set_title(
                f"Calibrated: {self.mm_per_pixel:.8f} mm/pixel | "
                "click measurement points in pairs"
            )

    def on_click(self, event):
        if event.inaxes is not self.ax or event.xdata is None or event.ydata is None:
            return

        point = (float(event.xdata), float(event.ydata))
        if self.straighten_mode:
            self.straighten_points.append(point)
            self.draw_straighten_point(point)
            if len(self.straighten_points) == 2:
                self.finish_straightening()
            self.figure.canvas.draw_idle()
            return

        if self.mm_per_pixel is None:
            if len(self.calibration_points) == 1:
                point = self.constrain_to_axis(self.calibration_points[-1], point)
            self.calibration_points.append(point)
            self.draw_calibration_point(point)
            if len(self.calibration_points) == 2:
                self.finish_calibration()
            self.figure.canvas.draw_idle()
            return

        if len(self.points) % 2 == 1:
            point = self.constrain_to_axis(self.points[-1], point)
        self.points.append(point)
        self.redraw_measurements()

    def start_straightening(self, _event):
        self.straighten_mode = True
        self.straighten_points.clear()
        self.update_title()
        self.figure.canvas.draw_idle()

    def draw_straighten_point(self, point):
        self.ax.plot(
            point[0], point[1], "o", markersize=9,
            markerfacecolor="cyan", markeredgecolor="black",
        )

    def finish_straightening(self):
        first, second = self.straighten_points
        angle = math.degrees(math.atan2(second[1] - first[1], second[0] - first[0]))
        self.image = self.image.rotate(
            angle,
            resample=Image.Resampling.BICUBIC,
            expand=True,
            fillcolor="white",
        )
        self.straighten_points.clear()
        self.straighten_mode = False
        self.calibration_points.clear()
        self.points.clear()
        self.mm_per_pixel = None
        self.artists.clear()
        self.calibration_artists.clear()
        self.ax.clear()
        self.ax.imshow(self.image)
        self.ax.set_xlabel("X (pixels)")
        self.ax.set_ylabel("Y (pixels)")
        self.update_title()
        messagebox.showinfo(
            "Image straightened",
            "The selected edge is now horizontal.\n"
            "Please calibrate the image again.",
        )

    def draw_calibration_point(self, point):
        artist, = self.ax.plot(
            point[0], point[1], "o", markersize=9,
            markerfacecolor="lime", markeredgecolor="black",
        )
        self.calibration_artists.append(artist)
        self.ax.annotate(
            f"cal {len(self.calibration_points)}", point,
            xytext=(7, 7), textcoords="offset points",
            color="lime", fontweight="bold",
            bbox={"facecolor": "black", "alpha": 0.7, "pad": 2},
        )

    def finish_calibration(self):
        first_x, first_y = self.calibration_points[0]
        second_x, second_y = self.calibration_points[1]
        pixel_distance = ((second_x - first_x) ** 2 + (second_y - first_y) ** 2) ** 0.5
        if pixel_distance <= 0:
            self.reset_calibration(None)
            return

        reference_mm = simpledialog.askfloat(
            "Calibration length",
            "Enter the known distance between the two selected points (mm):",
            minvalue=0.000001,
        )
        if reference_mm is None:
            self.calibration_points.clear()
            for artist in self.calibration_artists:
                artist.remove()
            self.calibration_artists.clear()
            for text in list(self.ax.texts):
                text.remove()
            self.update_title()
            self.figure.canvas.draw_idle()
            return

        self.mm_per_pixel = reference_mm / pixel_distance
        line, = self.ax.plot(
            [first_x, second_x], [first_y, second_y],
            color="lime", linewidth=2, label=f"Calibration: {reference_mm:g} mm",
        )
        self.calibration_artists.append(line)
        self.ax.legend(loc="upper right")
        self.update_title()
        messagebox.showinfo(
            "Calibration complete",
            f"Reference: {reference_mm:g} mm\n"
            f"Measured: {pixel_distance:.2f} pixels\n"
            f"Scale: {self.mm_per_pixel:.8f} mm/pixel",
        )

    def redraw_measurements(self):
        for artist in self.artists:
            artist.remove()
        self.artists.clear()
        for text in list(self.ax.texts):
            if text not in self.calibration_texts():
                text.remove()

        for index, (x, y) in enumerate(self.points, start=1):
            artist, = self.ax.plot(
                x, y, "o", markersize=7,
                markerfacecolor="yellow", markeredgecolor="black",
            )
            self.artists.append(artist)
            self.ax.annotate(
                str(index), (x, y), xytext=(7, 7),
                textcoords="offset points", color="yellow",
                fontweight="bold",
                bbox={"facecolor": "black", "alpha": 0.65, "pad": 2},
            )

            if index % 2 == 0:
                previous_x, previous_y = self.points[index - 2]
                line, = self.ax.plot(
                    [previous_x, x], [previous_y, y],
                    color="red", linewidth=1.5,
                )
                self.artists.append(line)
                distance_mm = self.pixel_distance(
                    (previous_x, previous_y), (x, y)
                ) * self.mm_per_pixel
                self.ax.annotate(
                    f"{distance_mm:.4f} mm",
                    ((previous_x + x) / 2, (previous_y + y) / 2),
                    xytext=(0, 6), textcoords="offset points",
                    color="red", fontsize=9,
                    bbox={"facecolor": "white", "alpha": 0.75, "pad": 1},
                )
        self.figure.canvas.draw_idle()

    def calibration_texts(self):
        return list(self.ax.texts)[:len(self.calibration_points)]

    @staticmethod
    def pixel_distance(first, second):
        return ((second[0] - first[0]) ** 2 + (second[1] - first[1]) ** 2) ** 0.5

    @staticmethod
    def constrain_to_axis(first, second):
        """Keep a pair of points on one exact horizontal or vertical axis."""
        if abs(second[0] - first[0]) >= abs(second[1] - first[1]):
            return second[0], first[1]
        return first[0], second[1]

    def undo_last(self, _event):
        if self.points:
            self.points.pop()
            self.redraw_measurements()

    def clear_points(self, _event):
        self.points.clear()
        self.redraw_measurements()

    def reset_calibration(self, _event):
        self.calibration_points.clear()
        self.mm_per_pixel = None
        for artist in self.calibration_artists:
            artist.remove()
        self.calibration_artists.clear()
        for text in list(self.ax.texts):
            text.remove()
        self.points.clear()
        self.redraw_measurements()
        self.update_title()
        self.figure.canvas.draw_idle()

    def save_csv(self, _event):
        if self.mm_per_pixel is None:
            messagebox.showinfo("Not calibrated", "Calibrate the image first.")
            return
        if len(self.points) < 2:
            messagebox.showinfo("No points", "Click at least two measurement points.")
            return

        output_path = filedialog.asksaveasfilename(
            title="Save measurements",
            initialfile=f"{self.image_path.stem}_measurements_mm.csv",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not output_path:
            return

        with open(output_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow([
                "point", "x_px", "y_px", "x_mm", "y_mm",
                "distance_from_previous_mm",
            ])
            for index, (x, y) in enumerate(self.points, start=1):
                distance = ""
                if index % 2 == 0:
                    distance = self.pixel_distance(
                        self.points[index - 2], (x, y)
                    ) * self.mm_per_pixel
                writer.writerow([
                    index, x, y, x * self.mm_per_pixel, y * self.mm_per_pixel,
                    distance,
                ])

        messagebox.showinfo("Saved", f"Measurements saved to:\n{output_path}")


def choose_image():
    root = tk.Tk()
    root.withdraw()
    selected_path = filedialog.askopenfilename(
        title="Select image",
        filetypes=[
            ("Image files", "*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp"),
            ("All files", "*.*"),
        ],
    )
    root.destroy()
    return Path(selected_path) if selected_path else None


def main():
    image_path = choose_image()
    if image_path is None:
        print("No image selected.")
        return
    tool = ImageMeasureTool(image_path)
    plt.show()


if __name__ == "__main__":
    main()
